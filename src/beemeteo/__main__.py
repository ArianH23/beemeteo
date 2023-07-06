import json
from datetime import datetime
import logging
from beemeteo.sources.cams import CAMS
from beemeteo.sources.darksky import DarkSky
from beemeteo.sources.meteogalicia import MeteoGalicia
from beemeteo.sources.appleweather import AppleWeather
import argparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sources = {
    "CAMS": CAMS,
    "DarkSky": DarkSky,
    "MeteoGalicia": MeteoGalicia,
    "AppleWeather": AppleWeather,
}


def historical(source, conf, latitude, longitude, date_from, date_to, data_file):
    """
    Gets raw data from source
    """
    source_ = sources.get(source)(conf)
    data = source_.get_historical_data(
        float(latitude),
        float(longitude),
        datetime.fromisoformat(date_from),
        datetime.fromisoformat(date_to)
    )
    data.to_csv(data_file, index=False)


def forecasting(source, conf, latitude, longitude, date_from, date_to, data_file):
    """
    Gets raw data from source
    """
    source_ = sources.get(source)(conf)
    data = source_.get_forecasting_data(
        float(latitude),
        float(longitude),
        datetime.fromisoformat(date_from),
        datetime.fromisoformat(date_to)
    )
    data.to_csv(data_file, index=False)


def collect_forecasting(source, conf, latitude, longitude):
    source_ = sources.get(source)(conf)
    data = source_.collect_forecasting(
        float(latitude),
        float(longitude),
    )

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    subprogram = ap.add_subparsers(help="The type of data to collect", dest="command", required=True)
    hist = subprogram.add_parser("historical", help="get historical data")
    fore = subprogram.add_parser("forecasting", help="get forecasting data")
    collect = subprogram.add_parser("collect_forecasting", help="collect forecasting data for now")

    # historical command
    hist.add_argument("-s", "--source", required=True,
                      help="The source to get data from", choices=["DarkSky", "CAMS", "MeteoGalicia"])
    hist.add_argument("-c", "--config", help="The configuration file path", required=True)
    hist.add_argument("-lat", "--latitude", help="The latitude", required=True)
    hist.add_argument("-lon", "--longitude", required=True, help="The longitude")
    hist.add_argument("-d1", "--date_from", required=True, help="The date to get weather from (isoformat)")
    hist.add_argument("-d2", "--date_to", required=True, help="The date to get weather to (isoformat)")
    hist.add_argument("-f", "--file", required=True, help="The file to store the data")

    fore.add_argument("-s", "--source", required=True,
                      help="The source to get data from", choices=["DarkSky", "CAMS", "MeteoGalicia"])
    fore.add_argument("-c", "--config", help="The configuration file path", required=True)
    fore.add_argument("-lat", "--latitude", help="The latitude", required=True)
    fore.add_argument("-lon", "--longitude", required=True, help="The longitude")
    fore.add_argument("-d1", "--date_from", required=True, help="The date to get weather from (isoformat)")
    fore.add_argument("-d2", "--date_to", required=True, help="The date to get weather to (isoformat)")
    fore.add_argument("-f", "--file", required=True, help="The file to store the data")

    collect.add_argument("-s", "--source", required=True,
                      help="The source to get data from", choices=["DarkSky", "CAMS", "MeteoGalicia"])
    collect.add_argument("-c", "--config", help="The configuration file path", required=True)
    collect.add_argument("-lat", "--latitude", help="The latitude", required=True)
    collect.add_argument("-lon", "--longitude", required=True, help="The longitude")
    args = ap.parse_args()

    with open(args.config) as config_f:
      config = json.load(config_f)

    if args.command == "historical":
        historical(args.source, config, args.latitude, args.longitude, args.date_from, args.date_to, args.file)
    elif args.command == "forecasting":
        forecasting(args.source, config, args.latitude, args.longitude, args.date_from, args.date_to, args.file)
    elif args.command == "collect_forecasting":
        collect_forecasting(args.source, config, args.latitude, args.longitude)
