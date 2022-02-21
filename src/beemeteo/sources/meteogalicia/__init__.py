import datetime

from io import StringIO

import pandas as pd
import pytz
import requests

from beemeteo.sources import Source, logger
from beemeteo.utils import _pandas_dt_to_ts_utc, _pandas_to_tz


class MeteoGalicia(Source):
    hbase_table_historical = "meteo_galicia_historical"
    hbase_table_forecasting = "meteo_galicia_forecasting"

    def __init__(self, config):
        super(MeteoGalicia, self).__init__(config)

    def _collect_forecasting(self, latitude, longitude, now, local_tz):
        now_timestamp = int(now.astimezone(pytz.UTC).timestamp())
        forecasted_data = self._get_historic_data_day(latitude, longitude, now, local_tz)
        forecasted_data.rename({"ts": "timestamp"}, axis=1, inplace=True)
        forecasted_data["latitude"] = latitude
        forecasted_data['longitude'] = longitude
        forecasted_data['forecasting_timestamp'] = now_timestamp
        forecasted_data = forecasted_data.query("timestamp >= {}".format(now_timestamp))
        return forecasted_data

    def _get_historical_data_source(self, latitude, longitude, gaps, local_tz):
        missing_data = pd.DataFrame()
        for ts_ini, ts_end in gaps:
            data_period = pd.DataFrame()
            # for each gap, get the date at instant 0 (we will always download the full day) the ts_end at 00,
            # is also downloaded at full
            ts_ini = local_tz.localize(datetime.datetime.combine(ts_ini.date(), datetime.datetime.min.time()))
            ts_end = local_tz.localize(datetime.datetime.combine(ts_end.date(), datetime.datetime.min.time()))
            logger.debug("No data for period {ts_ini} {ts_end}, downloading".format(ts_ini=ts_ini, ts_end=ts_end))

            # meteogalicia starts time of day at 1 UTC. We have to calculate if we need to request for another day.
            meteogalicia_start = pytz.UTC.localize(datetime.datetime.combine(ts_ini.date(), datetime.time(1))). \
                astimezone(local_tz)
            if meteogalicia_start > ts_ini:
                ts_ini_loop = ts_ini - datetime.timedelta(days=1)
            else:
                ts_ini_loop = ts_ini

            for day in pd.date_range(ts_ini_loop, ts_end, freq="1d"):
                logger.debug("downloading for day {}".format(day))
                daily_data = self._get_historic_data_day(latitude, longitude, day, local_tz)
                data_period = pd.concat([data_period, daily_data])
            data_period = data_period.sort_values(by=["ts"])
            data_period = data_period.query(
                "ts >= {} and ts <= {}".format(
                    ts_ini.timestamp(),
                    (ts_end + datetime.timedelta(hours=23)).timestamp()
                )
            )
            missing_data = pd.concat([missing_data, data_period])

        missing_data = missing_data.sort_values(by=["ts"])
        missing_data['latitude'] = latitude
        missing_data['longitude'] = longitude
        missing_data.drop_duplicates(subset=['latitude', 'longitude', 'ts'], inplace=True)
        key_cols = ["latitude", "longitude", "ts"]
        missing_data = missing_data.set_index(key_cols)[
            sorted(missing_data.columns[~missing_data.columns.isin(key_cols)])
        ].reset_index() if not missing_data.empty else missing_data
        return missing_data

    def _get_historic_data_day(self, latitude, longitude, day, local_tz):
        """
        Gets solar radiation information for a location on a given day

        :param latitude: station's latitude
        :param longitude: station's longitude
        :param day: day to retrieve data
        :return: all raw data for a given day
        """
        run = 0
        for resolution in [(4, 2), (12, 2), (12, 1), (36, 2), (36, 1)]:
            try:
                # Last 14 days of operational forecasts
                # http://mandeo.meteogalicia.es/
                # thredds/
                # ncss/
                # grid/
                # wrf_2d_04km/
                # fmrc/
                # files/
                # 20180423/
                # wrf_arw_det_history_d02_20180423_0000.nc4?
                # var=swflx&
                # point=true&
                # accept=csv&
                # longitude=0.62&
                # latitude=41.62&
                # temporal=all
                if (
                        (pytz.UTC.localize(datetime.datetime.utcnow()).astimezone(local_tz) -
                         day.astimezone(local_tz)).days <= 14
                ):
                    url_mg = (
                        "http://mandeo.meteogalicia.es/"
                        "thredds/"
                        "ncss/"
                        "grid/"
                        "wrf_2d_%02ikm/"
                        "fmrc/"
                        "files/"
                        "%s/"
                        "wrf_arw_det_history_d0%s_%s_%02i00.nc4?"
                        "var=swflx&"
                        "point=true&"
                        "accept=csv&"
                        "longitude=%s&"
                        "latitude=%s&"
                        "temporal=all"
                        % (
                            resolution[0],
                            datetime.datetime.strftime(day, "%Y%m%d"),
                            resolution[1],
                            datetime.datetime.strftime(day, "%Y%m%d"),
                            run,
                            longitude,
                            latitude,
                        )
                    )
                else:
                    # Historical forecasts. Only run 00 is available
                    # http://mandeo.meteogalicia.es/
                    # thredds/
                    # ncss/
                    # grid/
                    # modelos/
                    # WRF_HIST/
                    # d02/
                    # 2018/
                    # 01/
                    # wrf_arw_det_history_d02_20180122_0000.nc4?
                    # var=swflx&
                    # point=true&
                    # accept=csv&
                    # longitude=41.62&
                    # latitude=0.62&
                    # temporal=all
                    url_mg = (
                        "http://mandeo.meteogalicia.es/"
                        "thredds/"
                        "ncss/"
                        "grid/"
                        "modelos/"
                        "WRF_HIST/"
                        "d0%s"
                        "/%s"
                        "/%s"
                        "/wrf_arw_det_history_d0%s_%s_0000.nc4?"
                        "var=swflx&"
                        "point=true&"
                        "accept=csv&"
                        "longitude=%s&"
                        "latitude=%s&"
                        "temporal=all"
                        % (
                            resolution[1],
                            datetime.datetime.strftime(day, "%Y"),
                            datetime.datetime.strftime(day, "%m"),
                            resolution[1],
                            datetime.datetime.strftime(day, "%Y%m%d"),
                            longitude,
                            latitude,
                        )
                    )
                r = requests.get(url_mg)
                solar_data = pd.read_csv(StringIO(r.text), sep=",")
                if len(solar_data) == 0:
                    raise Exception(
                        "Location out of the bounding box, "
                        "trying with another resolution..."
                        "(Actual: " + str(resolution) + "km)"
                    )
                else:
                    solar_data = solar_data.rename(
                        columns={"date": "time", 'swflx[unit="W m-2"]': "GHI"}
                    )
                    solar_data["ts"] = _pandas_dt_to_ts_utc(
                        _pandas_to_tz(pd.to_datetime(solar_data["time"]), local_tz)
                    )
                    solar_data = solar_data[["ts", "GHI"]]
                    solar_data = solar_data.reset_index(drop=True)

                    return solar_data
            except Exception as e:
                logger.error(e)
        return pd.DataFrame({})
