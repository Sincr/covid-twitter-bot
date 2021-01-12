uk_params = {
    "filter": "areaType=overview",
    "structure": {
        "Date": "date",
        "Area": "areaName",
        "DailyCasesSpecimen": "newCasesBySpecimenDate"
    },
    "population": 66796881
}

ey_params = {
    "filter": "areaType=utla;areaName=East Riding Of Yorkshire",
    "structure": {
        "Date": "date",
        "Area": "areaName",
        "DailyCasesSpecimen": "newCasesBySpecimenDate",
        "DailyCasesReported": "newCasesByPublishDate",
        "DailyDeaths": "newDeaths28DaysByPublishDate",
        "CumulativeDeaths": "cumDeaths28DaysByPublishDate"
    },
    "population": 341173
}

hull_params = {
    "filter": "areaType=utla;areaName=Kingston upon Hull, City of",
    "structure": ey_params["structure"],
    "population": 259778
}