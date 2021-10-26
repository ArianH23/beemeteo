import datetime as dt
import io

import pandas as pd
import pytz
import requests
from dateutil.relativedelta import relativedelta

VERSION = "1.0.0"
SODA_SERVER_SERVICE = "http://www.soda-is.com/service/wps"
SODA_SERVER_MIRROR_SERVICE = "http://pro.soda-is.com/service/wps"


def to_tz(ts, timezone):
    return (
        ts.astimezone(pytz.UTC)
        if ts.tzinfo is not None
        else timezone.localize(ts).astimezone(pytz.UTC)
    )


class SODA:
    def __init__(self, cams_registered_mails):
        self.cams_registered_mails = cams_registered_mails
        assert len(self.cams_registered_mails) > 0

    def solar_radiation(self, latitude, longitude, timezone, day):
        """
        Gets solar radiation information for a location on a given day

        :param float latitude: longitude
        :param float longitude: latitude
        :param timezone: timezone
        :param datetime.datetime day:
        :return:
        """
        date_begin = to_tz(day, timezone)
        date_end = to_tz(
            day + relativedelta(days=1) - relativedelta(seconds=1), timezone
        )
        for mail in self.cams_registered_mails:
            try:
                response = self._request(
                    mail, latitude, longitude, date_begin, date_end
                )
                return response
            except Exception:
                continue

    def _request_server(
        self,
        server,
        username,
        latitude,
        longitude,
        date_begin,
        date_end,
        altitude,
        time_ref,
        summarization,
    ):
        payload = {
            "Service": "WPS",
            "Request": "Execute",
            "Identifier": "get_cams_radiation",
            "version": VERSION,
            "DataInputs": "latitude={};longitude={};altitude={};"
            "date_begin={};date_end={};time_ref={};summarization={};username={}".format(
                latitude,
                longitude,
                altitude,
                dt.datetime.strftime(date_begin, "%Y-%m-%d %H:%M:%S")[:10],
                dt.datetime.strftime(date_end, "%Y-%m-%d %H:%M:%S")[:10],
                time_ref,
                summarization,
                username.replace("@", "%2540"),
            ),
            "RawDataOutput": "irradiation",
        }

        params = "&".join("%s=%s" % (k, v) for k, v in payload.items())
        response = requests.get(server, params=params)
        if response.status_code != 200:
            raise Exception
        return self._parse_request(response)

    def _request(
        self,
        username,
        latitude,
        longitude,
        date_begin,
        date_end,
        altitude=-999,
        time_ref="UT",
        summarization="PT01H",
    ):
        try:
            response = self._request_server(
                SODA_SERVER_SERVICE,
                username,
                latitude,
                longitude,
                date_begin,
                date_end,
                altitude,
                time_ref,
                summarization,
            )
        except Exception:
            response = self._request_server(
                SODA_SERVER_MIRROR_SERVICE,
                username,
                latitude,
                longitude,
                date_begin,
                date_end,
                altitude,
                time_ref,
                summarization,
            )
        return response

    @staticmethod
    def _parse_request(response):
        """Parse the request output into a pandas DataFrame.
        :param response: api response
        :return: dataframe
        """

        data = io.StringIO(response.text.split("#")[-1])
        df = pd.read_csv(data, delimiter=";")
        return df
