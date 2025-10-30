# Next Scrapers to Build

This document lists venues and event sources that should be prioritized for scraper development.

## High Priority Venues

### Music Venues
- [ ] **Shapeshifter Plus** - https://shapeshifterplus.org/events/list/
- [ ] **Concerts on the Slope** - https://www.concertsontheslope.org/
- [X] **Union Hall** - https://unionhallny.com/calendar
- [ ] **Littlefield** - https://littlefieldnyc.com/
- [ ] **Public Records** - https://publicrecords.nyc/
- [ ] **333 Lounge** - https://www.333lounge.com/
- [ ] **Barbès** - https://www.barbesbrooklyn.com/events
- [X] **The Bell House** - https://www.thebellhouseny.com/shows
- [X] **Farm One** - https://www.farm.one/

### Comedy Venues
- [ ] **Eastville Comedy** - https://www.eastvillecomedy.com/calendar/2025-11
- [ ] **The Rat** - https://www.theratnyc.com/event-list
- [ ] **Park Slope Comedy** (Eventbrite) - https://www.eventbrite.com/o/park-slop-comedy-107287434501

### Theater & Performance
- [ ] **Gallery Players** - https://www.galleryplayers.com/
- [ ] **The Joyce** - https://www.joyce.org/
- [ ] **NYTW** (New York Theatre Workshop) - https://www.nytw.org/
- [ ] **Minetta Lane Theatre**
- [ ] **Cherry Lane Theatre**
- [ ] **St. Ann's Warehouse**
- [ ] **92nd Street Y**

### Major Concert Halls
- [ ] **Beacon Theatre**
- [ ] **The Stand**
- [ ] **Radio City Music Hall**
- [ ] **Town Hall**
- [ ] **Carnegie Hall – Stern Auditorium**
- [ ] **Hammerstein Ballroom**
- [ ] **NYU Skirball Center**
- [ ] **Lincoln Center – Rose Theater / Alice Tully Hall**
- [ ] **Sony Hall**
- [ ] **BMCC Tribeca**
- [ ] **Perelman Performing Arts Center**

## Existing Scrapers to Update

### Brooklyn Museum - Add Music Filter
- [ ] **Update existing scraper** - https://www.brooklynmuseum.org/programs?eventType=Music
  - Current scraper: `src/scrapers/brooklyn_museum.js`
  - Add filter for music events specifically

### Brooklyn Public Library
- [ ] **BPL Presents** - https://discover.bklynlibrary.org/?event=true&eventtags=BPL+Presents

## Community & Local Events

### Bookstores & Community Spaces
- [ ] **FNL BK** - https://www.fnlbk.com/upcoming
- [ ] **Community Bookstore** - https://www.communitybookstore.net/events

### Event Aggregators
- [ ] **Brooklyn Paper Events** - https://events.brooklynpaper.com/
- [ ] **Downtown Brooklyn Events** - https://downtownbrooklyn.com/events/
- [ ] **DoNYC** - https://donyc.com/

## Research Sources

### Newsletters & Guides
- [ ] **Brooklyn Magazine Weekend Guide** - https://www.bkmag.com/2025/10/22/what-to-do-in-brooklyn-this-weekend-guide/
  - Consider for event discovery and validation

## Development Notes

### Priority Order
1. **Music venues** (shapeshifter, union hall, littlefield) - high event volume
2. **Comedy venues** (eastville, the rat) - regular programming
3. **Major concert halls** - high-value events
4. **Theater venues** - cultural events
5. **Community spaces** - local events
6. **Event aggregators** - comprehensive coverage

### Technical Considerations
- **Eventbrite integration** - Park Slope Comedy uses Eventbrite
- **Filtered views** - Brooklyn Museum music filter
- **Calendar formats** - Various date formats across venues
- **Pagination** - Some venues may have extensive event lists

### Venue Categories
- **Music**: Shapeshifter Plus, Union Hall, Littlefield, Public Records, 333 Lounge, Barbès, The Bell House, Farm One
- **Comedy**: Eastville Comedy, The Rat, Park Slope Comedy
- **Theater**: Gallery Players, The Joyce, NYTW, Minetta Lane, Cherry Lane, St. Ann's Warehouse, 92nd Street Y
- **Concert Halls**: Beacon Theatre, The Stand, Radio City Music Hall, Town Hall, Carnegie Hall, Hammerstein Ballroom, NYU Skirball Center, Lincoln Center, Sony Hall, BMCC Tribeca, Perelman Performing Arts Center
- **Community**: FNL BK, Community Bookstore
- **Aggregators**: Brooklyn Paper Events, Downtown Brooklyn Events, DoNYC

## Status Legend
- [ ] Not started
- [🔄] In progress (staging)
- [✅] Completed (production)
- [⚠️] Needs updates
