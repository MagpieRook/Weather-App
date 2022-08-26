#!/usr/bin/env python3
import csv
import json
import operator
from datetime import date
from typing import Dict, List, Union

import click

DEFAULT_FILE_NAME = "noaa_historical_weather_10yr.csv"


def float_catch(string: str) -> Union[float, None]:
    """
    Converts string to float but catches a ValueError.
    """
    if len(string) == 0:
        return float(0)
    try:
        return float(string)
    except ValueError as e:
        click.echo(
            message=f"Could not parse value to float: {string}, {e}", err=True
        )  # noqa
        return None


class Date:
    def __init__(
        self,
        day: date,
        precipitation: float,
        snowfall: float,
        max_temp: float,
        min_temp: float,
    ):
        self.date = day
        self.precipitation = precipitation
        self.snowfall = snowfall
        self.max_temp = max_temp
        self.min_temp = min_temp

    def temp_delta(self) -> float:
        return self.max_temp - self.min_temp

    def total_precipitation(self) -> float:
        return self.precipitation + self.snowfall


class DataEncoder(json.JSONEncoder):
    def default(self, o):
        if type(o) is Date:
            return o.__dict__
        elif type(o) is date:
            return str(o)
        else:
            return super().default(o)


def read_file(file_name: str) -> Dict[str, List[Date]]:
    """
    Takes "NAME", "DATE", "PRCP", "SNOW", "TMAX", and "TMIN" fields
    from the CSV file at the destination provided.
    Returns the formatted data from the file.
    """
    data = {}
    with open(file_name, newline="") as f:
        reader = csv.reader(f)
        # Get and format headers required for data processing
        headers = reader.__next__()
        data_pos = {
            "NAME": -1,
            "DATE": -1,
            "PRCP": -1,
            "SNOW": -1,
            "TMAX": -1,
            "TMIN": -1,
        }
        for n, header in enumerate(headers):
            if header in data_pos:
                data_pos[header] = n

        if -1 in data_pos.values():
            click.echo(
                message=f"Improperly formatted CSV. Missing {', '.join([header for (header, pos) in data_pos if pos == -1])}",  # noqa
                err=True,
            )
            return

        # Get and format data based on headers
        for n, row in enumerate(reader):
            # "MIAMI INTERNATIONAL AIRPORT, FL US" -> "miami"
            # "JUNEAU AIRPORT, AK US" -> "juneau"
            # "BOSTON, MA US" -> "boston"
            name = row[data_pos["NAME"]].split(" ")[0].lower().replace(",", "")
            if name not in data:
                data[name] = []

            # "1900-01-01" -> date(1900, 01, 01)
            ymd = row[data_pos["DATE"]].split("-")
            try:
                ymd = [int(d) for d in ymd]
                day = date(*ymd)
            except (ValueError, TypeError) as e:
                click.echo(
                    message=f"Could not parse date provided for row {n}: {ymd}, {e}",  # noqa
                    err=True,
                )
                continue

            precipitation = float_catch(row[data_pos["PRCP"]])
            snowfall = float_catch(row[data_pos["SNOW"]])
            max_temp = float_catch(row[data_pos["TMAX"]])
            min_temp = float_catch(row[data_pos["TMIN"]])
            if None in [precipitation, snowfall, max_temp, min_temp]:
                click.echo(
                    message=f"Could not parse weather data for row {n}: {data_pos}",  # noqa
                    err=True,
                )
                continue

            data[name].append(
                Date(day, precipitation, snowfall, max_temp, min_temp)
            )  # noqa

    return data


@click.group()
def cli():
    pass


@click.command()
@click.argument("city")
def days_of_precip(city: str):
    if city not in ("bos", "jnu", "mia"):
        click.echo(
            message="City not recognized. Please use one of 'bos', 'jnu', 'mia'",  # noqa
            err=True,
        )
        return

    data = read_file(DEFAULT_FILE_NAME)
    # could clean this up by parsing the data dictionary names
    # though would merely move this switch case to the read_file func
    if city == "bos":
        data = data["boston"]
    elif city == "jnu":
        data = data["juneau"]
    elif city == "mia":
        data = data["miami"]

    dates_with_precip = [d.date for d in data if d.total_precipitation() > 0]

    year_days = {}
    for d in dates_with_precip:
        if d.year not in year_days:
            year_days[d.year] = 0

        year_days[d.year] += 1

    click.echo(
        json.dumps(
            {
                "city": city,
                "days_of_precip": (
                    sum(year_days.values()) / len(year_days.keys())
                ),  # noqa
            },
            indent=4,
        )
    )


@click.command()
@click.option(
    "-y",
    "--year",
    type=int,
    help="The year to parse (a number from 2010-2019)",
)  # noqa
@click.option(
    "-m",
    "--month",
    type=int,
    help="The month to parse in number form (1-12)",
)
@click.argument("city")
def max_temp_delta(year: int, month: int, city: str):
    if city not in ("bos", "jnu", "mia"):
        click.echo(
            message="City not recognized. Please use one of 'bos', 'jnu', 'mia'",  # noqa
            err=True,
        )
        return
    if year is not None and (year >= 2020 or year < 2010):
        click.echo(
            message="Please provide a year from 2010 to 2019",
            err=True,
        )
        return
    if month is not None:
        if month > 12 or month < 1:
            click.echo(
                message="Please provide a number for a month from 1 (January) to 12 (December)",  # noqa
                err=True,
            )
            return
        if year is None:
            click.echo(
                message="Year is required if month is provided. Please provide a year from 2010 to 2019",  # noqa
                err=True,
            )
            return

    data = read_file(DEFAULT_FILE_NAME)
    # could clean this up by parsing the data dictionary names
    # though would merely move this switch case to the read_file func
    if city == "bos":
        data = data["boston"]
    elif city == "jnu":
        data = data["juneau"]
    elif city == "mia":
        data = data["miami"]

    if month is not None:
        tdeltas = [
            (d.date, d.temp_delta())
            for d in data
            if d.date.month == month and d.date.year == year
        ]
    elif year is not None:
        tdeltas = [
            (d.date, d.temp_delta()) for d in data if d.date.year == year
        ]  # noqa
    else:
        tdeltas = [(d.date, d.temp_delta()) for d in data]

    date_max_delta = max(tdeltas, key=operator.itemgetter(1))
    click.echo(
        json.dumps(
            {
                "city": city,
                "date": date_max_delta[0],
                "temp_change": round(date_max_delta[1], 14),
            },
            indent=4,
            cls=DataEncoder,
        )
    )


if __name__ == "__main__":
    cli.add_command(days_of_precip)
    cli.add_command(max_temp_delta)
    cli()
