# Overview

This is a depop shop scraping project. The idea is to collect items based on a search prompt, filter out only those that have likes and offers above the minimal threshold. Then select top 20 items. Parse out their price, name, url, img url, likes, offers.
The goal of this is to create an automated tool for dropshipping needs, that will find the best trending/selling articles and their prices based on the search query, that the user may then use to find similar products on sites like Aliexpress (the search is going to be manual for mvp).

## Specs
uv, python, curl_cffi, loguru, pydantic
database: SQLite, csv and json for output

## Antibot defense
The website features some sort of antibot defense, meaning that bare postman calls get 403. But curl_cffi with chrome 124 impersonation direct api calls to needed endpoints seems to do the trick. The limit of items for one api call is around 160. The total number of items is shown

## Todo
- [ ] Analyse raw data response
- [ ] Create a data scheme
- [ ] Create config files
- [ ] Set up a logger
- [ ] Build the cycling/pagination logic on top of main.py so that it cycles trhough all the products that meet the threshold requirements, with a small delay to not get banned
- [ ] Create a parser for stored data
- [ ] Craete argparse for search query and optional test arg to test the endpoint collecting only first 16 items for analysis