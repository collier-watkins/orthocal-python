import functools
import logging

from datetime import date, datetime, timedelta, timezone

from asgiref.sync import async_to_sync
from django.db.models import Q
from django.utils.functional import cached_property
from phonetics import metaphone
from thefuzz import fuzz

from . import datetools, models
from .datetools import Weekday, FastLevels, FastLevelDesc, FastExceptions, FloatIndex
from commemorations.models import Commemoration

logger = logging.getLogger(__name__)

async def amonth_of_days(year, month, use_julian=False):
    dt = datetime(year, month, 1)
    while dt.month == month:
        day = Day(dt.year, dt.month, dt.day, use_julian=use_julian)
        await day.ainitialize()
        yield day
        dt += timedelta(days=1)

def month_of_days(year, month, use_julian=False):
    dt = datetime(year, month, 1)
    while dt.month == month:
        day = Day(dt.year, dt.month, dt.day, use_julian=use_julian)
        day.initialize()
        yield day
        dt += timedelta(days=1)


@functools.cache
class Day:
    def __init__(self, year, month, day, use_julian=False, do_jump=True):
        self.gregorian_date = date(year=year, month=month, day=day)

        if use_julian:
            dt = datetools.gregorian_to_julian(year, month, day)
        else:
            dt = self.gregorian_date

        self.date = dt
        self.year = dt.year
        self.month = dt.month
        self.day = dt.day
        self.do_jump = do_jump

        if use_julian:
            pdist, pyear = datetools.compute_julian_pascha_distance(dt)
            self.jdn = datetools.julian_to_jdn(dt)
        else:
            pdist, pyear = datetools.compute_pascha_distance(dt)
            self.jdn = datetools.gregorian_to_jdn(dt)

        self.pdist = pdist
        self.weekday = datetools.weekday_from_pdist(pdist)

        self.pyear = Year(pyear, use_julian)

        self._initialized = False

    async def ainitialize(self):
        if not self._initialized:
            await self._collect_commemorations()
            await self._add_supplemental_commemorations()
            self._apply_fasting_adjustments()
            self._initialized = True

    initialize = async_to_sync(ainitialize)

    def __str__(self):
        return str(self.date)

    @cached_property
    def summary_title(self):
        if self.weekday == 0 or -9 < self.pdist < 7:
            if self.titles:
                return '; '.join(self.titles)

        if self.feasts:
            return '; '.join(self.feasts)

        if self.saints:
            return '; '.join(self.minimal_saints)

        if self.titles:
            return '; '.join(self.titles)

    async def _collect_commemorations(self):
        q = Q(pdist=self.pdist)

        if float_index := self.pyear.floats.get(self.pdist):
            q |= Q(pdist=float_index)

        q |= Q(month=self.month, day=self.day)

        days = [d async for d in models.Day.objects.filter(q)]

        self.titles = [title for d in days if (title := d.full_title)]
        self.saints = [d.saint for d in days if d.saint]
        self.minimal_saints = [d.saint for d in days if d.saint]
        self.feasts = [d.feast_name for d in days if d.feast_name]
        self.service_notes = [d.service_note for d in days if d.service_note]

        self.feast_level = max(d.feast_level for d in days)
        self.fast_level = max(d.fast for d in days)
        self.fast_exception = max(d.fast_exception for d in days)

    async def _add_supplemental_commemorations(self):
        """Add additional commemorations and writeups from Abbamoses.com."""

        def match(str1, str2):
            """Combine a phonetic algorithm with fuzzy matching to try and align the two datasets."""
            s1 = ' '.join(metaphone(w) for w in str1.split() if w.isalpha())
            s2 = ' '.join(metaphone(w) for w in str2.split() if w.isalpha())
            return fuzz.partial_token_sort_ratio(s1, s2)

        self.stories = [s async for s in Commemoration.objects.filter(month=self.month, day=self.day)]

        if not self.stories:
            return

        stories = self.stories.copy()
        commemorations = self.titles + self.feasts + self.saints

        # Find stories that match the existing commemorations
        for c in commemorations:
            scores = [(s, match(c, s.title)) for s in stories]
            scores.sort(key=lambda x: x[1], reverse=True)
            story, score = scores[0]
            if score > 60:
                # The story matched an already existing commemoration, so we
                # don't add it to the commemorations again.
                stories.remove(story)

            if not stories:
                # We matched all the stories
                break

        # Add unmatched stories to the list of commemorations
        self.saints.extend(s.title for s in stories)
        
    def _apply_fasting_adjustments(self):
        # Adjust for fast free days
        if self.fast_exception == 11:
            self.fast_level = FastLevels.NoFast
            self.fast_level_desc = FastLevelDesc[self.fast_level]
            return

        # Are we in the Apostles fast?
        if 56 < self.pdist < self.pyear.peter_and_paul:
            self.fast_level = FastLevels.ApostlesFast
            if self.pdist == 57:
                self.service_notes.append("Beginning of Apostles' Fast")

        match self.fast_level:
            case FastLevels.LentenFast:
                # Remove fish for minor feast days in Lent
                if self.fast_exception == 2:
                    self.fast_exception -= 1
            case FastLevels.DormitionFast:
                # Allow wine and oil on weekends during the Dormition fast
                if self.weekday in (Weekday.Sunday, Weekday.Saturday) and self.fast_exception == 0:
                    self.fast_exception += 1
            case FastLevels.ApostlesFast | FastLevels.NativityFast:
                match self.weekday:
                    case Weekday.Tuesday | Weekday.Thursday:
                        if self.fast_exception == 0:
                            self.fast_exception += 1
                    case Weekday.Wednesday | Weekday.Friday:
                        if self.feast_level < 4 and self.fast_exception > 1:
                            self.fast_exception = 1
                    case Weekday.Sunday | Weekday.Saturday:
                        self.fast_exception = 2

                # Ease restrictions during the week before Nativity
                if self.pyear.nativity-6 < self.pdist < self.pyear.nativity-1 and self.fast_exception > 1:
                    self.fast_exception = 1

        # The days before Nativity and Theophany are wine and oil days
        if self.pdist in (self.pyear.nativity-1, self.pyear.theophany-1) and self.weekday in (Weekday.Sunday, Weekday.Saturday):
            self.fast_exception = 1

        self.fast_level_desc = FastLevelDesc[self.fast_level]
        self.fast_exception_desc = FastExceptions[self.fast_exception]

    @cached_property
    def feast_level_desc(self):
        return datetools.FeastLevels[self.feast_level]

    @cached_property
    def fast_level_desc(self):
        return datetools.FastLevels[self.fast_level]

    @cached_property
    def fast_exception_desc(self):
        return datetools.FastExceptions[self.fast_exception]

    @cached_property
    def has_no_memorial(self):
        """True if Memorial Saturday is cancelled."""
        return self.pdist in (-36, -29, -22) and self.month == 3 and self.day in (9, 24, 25, 26)

    @cached_property
    def has_matins_gospel(self):
        """True if there could be a non-Eothinon Gospel reading for Matins, otherwise False."""

        if self.weekday != Weekday.Sunday:
            return True

        if -8 < self.pdist < 50:
            return False

        if self.feast_level < 7:
            return False

        return True

    @cached_property
    def preceding_pdist(self):
        """The number of days from the Pascha preceding this day to this day."""
        return self.pdist if self.pdist >= 0 else self.jdn - self.pyear.previous_pascha

    @cached_property
    def tone(self):
        """The proper tone for this day."""

        # See https://mci.archpitt.org/liturgy/EightTones.html

        # The last day of Lent is on the Friday before Lazarus Saturday. From
        # Lazarus Saturday until Holy Saturday, the octoechoes are not employed.
        if -9 < self.pdist < 0:
            return 0

        # Bright week is different. We cycle through the tones one per day, skipping tone 7.
        # Tone 7 is said to be too somber for bright week.
        if 0 <= self.pdist < 7:
            bright_tones = 1, 2, 3, 4, 5, 6, 8
            return bright_tones[self.pdist]

        # TODO: check for great feasts and set tone to 0 for them
        pass

        # We start the cycle with Thomas Sunday, which has pdist == 7 and so is
        # the 1st Sunday (7 // 7 == 1).  The mod cycle is 0 origin, so 0-7 for
        # mod 8. We add 1 to shift it to 1-8.
        nth_sunday = self.preceding_pdist // 7
        return (nth_sunday-1) % 8 + 1

    @cached_property
    def eothinon_gospel(self):
        """The number of the Sunday Eothinon Gospel if relevant, otherwise None."""

        if self.weekday != Weekday.Sunday:
            return None

        # There are no matins gospels from Holy Week until Pentecost
        if -8 < self.pdist < 50:
            return None

        # high ranking feasts preempt the Eothinon
        if self.feast_level >= 7:
            return None

        # Compute the number of the correct Eothinon Gospel.  We cycle through
        # the 11 gospels starting on the 1st Sunday after Pentecost.
        nth_sunday = (self.preceding_pdist - 49) // 7
        return (nth_sunday - 1) % 11 + 1

    @cached_property
    def has_no_paremias(self):
        """True if the paremias for this day have been moved."""
        return self.pyear.has_no_paremias(self.pdist)

    @cached_property
    def has_moved_paremias(self):
        """True if this day has moved paremias for the succeeding day."""
        return self.pyear.has_moved_paremias(self.pdist)

    async def aget_readings(self, fetch_content=False):
        """A list of lectionary readings."""

        if hasattr(self, 'readings'):
            # Grab cached readings if we already have them
            if fetch_content:
                for reading in self.readings:
                    await reading.pericope.aget_passage()

            return self.readings

        query = Q(pdist=self.pdist) & ~Q(source='Gospel') & ~Q(source='Epistle')

        if self.gospel_pdist is not None:
            if self.has_no_memorial:
                query |= Q(pdist=self.gospel_pdist, source='Gospel') & ~Q(desc='Departed')
            else:
                query |= Q(pdist=self.gospel_pdist, source='Gospel')

        if self.epistle_pdist is not None:
            if self.has_no_memorial:
                query |= Q(pdist=self.epistle_pdist, source='Epistle') & ~Q(desc='Departed')
            else:
                query |= Q(pdist=self.epistle_pdist, source='Epistle')

        # include floats
        if float_index := self.pyear.floats.get(self.pdist):
            query |= Q(pdist=float_index)

        # Add Matins Eothinon gospel
        if self.eothinon_gospel:
            query |= Q(pdist=self.eothinon_gospel + 700)

        # add paremias
        if self.has_moved_paremias:
            # Grab the paremias from the succeeding day since it has been moved back 1 day
            dt = self.date + timedelta(days=1)
            query |= Q(month=dt.month, day=dt.day, source='Vespers')

        # build conditional using month/day instead of pdist

        subquery = Q(month=self.month, day=self.day)
        if not self.has_matins_gospel:
            subquery &= ~Q(source='Matins Gospel')

        if self.has_no_paremias:
            subquery &= ~Q(source='Vespers')

        if self.month == 3 and self.day == 26 and self.weekday in [Weekday.Monday, Weekday.Tuesday, Weekday.Thursday]:
            # There are no readings for leavetaking of Annunciation on a non-liturgy day
            subquery &= ~Q(desc='Theotokos')

        query |= subquery

        # Do select_related to avoid later synchronous foreign key lookup
        queryset = models.Reading.objects.filter(query).select_related('pericope')

        # Generate the list of readings
        self.readings = []
        async for reading in queryset.order_by('ordering'):
            if fetch_content:
                await reading.pericope.aget_passage()

            if -42 < self.pdist < -7 and self.feast_level < 7 and reading.source == 'Matins Gospel':
                # Place Lenten Matins Gospel at the top
                self.readings.insert(0, reading)
            else:
                self.readings.append(reading)

        return self.readings

    get_readings = async_to_sync(aget_readings)

    async def aget_minimal_readings(self, fetch_content=False):
        """Get just the first Epistle and Gospel if available."""

        readings = await self.aget_readings()

        epistles = [r for r in readings if r.source == 'Epistle']
        gospels = [r for r in readings if r.source == 'Gospel']

        if epistles and gospels:
            return [epistles[0], gospels[0]]
        else:
            return readings
        
    @cached_property
    def jump(self):
        """The Lucan jump appropriate for this day."""
        return self.pyear.lucan_jump if self.do_jump and self.pdist > self.pyear.sun_after_elevation else 0

    @cached_property
    def has_daily_readings(self):
        """True if daily readings are not suppressed for this day."""
        return self.pyear.has_daily_readings(self.pdist)

    @cached_property
    def epistle_pdist(self):
        """Adjusted pdist for the epistle."""

        if self.has_daily_readings:
            if self.pdist == 252:
                return self.pyear.forefathers
            elif self.pdist > 272:
                return self.jdn - self.pyear.next_pascha
            else:
                return self.pdist

    @cached_property
    def gospel_pdist(self):
        """Adjusted pdist for the Gospel."""

        if self.has_daily_readings:
            limit = 279 if datetools.weekday_from_pdist(self.pyear.theophany) < Weekday.Tuesday else 272

            if self.pdist == 245 - self.pyear.lucan_jump:
                return self.pyear.forefathers + self.pyear.lucan_jump
            elif self.pdist > self.pyear.sun_after_theophany and self.weekday == Weekday.Sunday and self.pyear.extra_sundays > 1:
                i = (self.pdist - self.pyear.sun_after_theophany) // 7
                return self.pyear.reserves[i-1]
            elif self.pdist + self.jump > limit:
                # Theophany stepback
                return self.jdn - self.pyear.next_pascha
            else:
                return self.pdist + self.jump


@functools.cache
class Year:
    def __init__(self, year, use_julian=False):
        self.year = year
        self.use_julian = use_julian
        self.pascha = datetools.compute_pascha_jdn(year)

        (self.sat_before_elevation,
         self.sun_before_elevation,
         self.sat_after_elevation,
         self.sun_after_elevation) = datetools.surrounding_weekends(self.elevation)

        (self.sat_before_theophany,
         self.sun_before_theophany,
         self.sat_after_theophany,
         self.sun_after_theophany) = datetools.surrounding_weekends(self.theophany)

        (self.sat_before_nativity,
         self.sun_before_nativity,
         self.sat_after_nativity,
         self.sun_after_nativity) = datetools.surrounding_weekends(self.nativity)


    @cached_property
    def previous_pascha(self):
        return datetools.compute_pascha_jdn(self.year - 1)

    @cached_property
    def next_pascha(self):
        return datetools.compute_pascha_jdn(self.year + 1)

    def has_daily_readings(self, pdist):
        return pdist not in self.no_daily

    def has_moved_paremias(self, pdist):
        return self.paremias.get(pdist) is True

    def has_no_paremias(self, pdist):
        return self.paremias.get(pdist) is False

    @cached_property
    def no_daily(self):
        """Return a set() of days on which daily readings are suppressed"""

        no_daily = {
                self.sun_before_theophany, self.sun_after_theophany, self.theophany-5,
                self.theophany-1, self.theophany, self.forefathers,
                self.sun_before_nativity, self.nativity-1, self.nativity,
                self.nativity+1, self.sun_after_nativity,
        }

        if self.sat_after_theophany == self.theophany+1:
            no_daily.add(self.sat_after_theophany)

        if datetools.weekday_from_pdist(self.annunciation) == Weekday.Saturday:
            no_daily.add(self.annunciation)

        return no_daily

    @cached_property
    def theophany(self):
        return self.date_to_pdist(1, 6, self.year+1)

    @cached_property
    def finding(self):
        return self.date_to_pdist(2, 24, self.year)

    @cached_property
    def annunciation(self):
        return self.date_to_pdist(3, 25, self.year)

    @cached_property
    def peter_and_paul(self):
        return self.date_to_pdist(6, 29, self.year)

    @cached_property
    def beheading(self):
        return self.date_to_pdist(8, 29, self.year)

    @cached_property
    def nativity_theotokos(self):
        return self.date_to_pdist(9, 8, self.year)

    @cached_property
    def elevation(self):
        return self.date_to_pdist(9, 14, self.year)

    @cached_property
    def nativity(self):
        return self.date_to_pdist(12, 25, self.year)

    @cached_property
    def fathers_six(self):
        # The Fathers of the Sixth Ecumenical Council falls on the Sunday nearest 7/16
        pdist = self.date_to_pdist(7, 16, self.year)
        weekday = datetools.weekday_from_pdist(pdist)
        if weekday < Weekday.Thursday:
            return pdist - weekday
        else:
            return pdist + 7 - weekday

    @cached_property
    def fathers_seven(self):
        # The Fathers of the Seventh Ecumenical Council falls on the Sunday
        # following 10/11 or 10/11 itself if it is a Sunday.
        pdist = self.date_to_pdist(10, 11, self.year)
        weekday = datetools.weekday_from_pdist(pdist)
        if weekday > Weekday.Sunday:
            pdist += 7 - weekday
        return pdist

    @cached_property
    def demetrius_saturday(self):
        # Demetrius Saturday is the Saturday before 10/26
        pdist = self.date_to_pdist(10, 26, self.year)
        return pdist - datetools.weekday_from_pdist(pdist) - 1

    @cached_property
    def synaxis_unmercenaries(self):
        # The Synaxis of the Unmercenaries is the Sunday following 11/1
        pdist = self.date_to_pdist(11, 1, self.year)
        return pdist + 7 - datetools.weekday_from_pdist(pdist)

    @cached_property
    def forefathers(self):
        # Forefathers Sunday is the week before the week of Nativity
        weekday = datetools.weekday_from_pdist(self.nativity)
        return self.nativity - 14 + ((7 - weekday) % 7)

    @cached_property
    def lucan_jump(self):
        # 168 - (Sunday after Elevation)
        return 168 - (self.elevation + 7 - datetools.weekday_from_pdist(self.elevation))

    @cached_property
    def extra_sundays(self):
        return (self.next_pascha - self.pascha - 84 - self.sun_after_theophany) // 7

    @cached_property
    def reserves(self):
        """Return a list of pascha distances for days with unread Sunday gospels"""

        reserves = []

        if self.extra_sundays:
            first = self.forefathers + self.lucan_jump + 7
            reserves.extend(range(first, 267, 7))
            if remainder := self.extra_sundays - len(reserves):
                start = 175 - remainder * 7
                reserves.extend(range(start, 169, 7))

        return reserves

    @cached_property
    def paremias(self):
        """Return a table of paremias that should be moved."""

        # minor feasts on weekdays in lent have their paremias moved to previous day

        paremias = {}

        # These seem to be feasts with 3 <= FeastLevel <= 5. We could probably
        # grab this from the database at run time.
        days = (
                (2, 24),    # 1st and 2nd finding of the head of John the Baptist
                (2, 27),    # St. Raphael, Bishop of Brooklyn
                (3, 9),     # Holy Forty Martyrs of Sebaste
                (3, 31),    # Repose St Innocent, Metr. Moscow and Apostle to Americas
                (4, 7),     # Repose St. Tikhon, Patriarch of Moscow, Enlightener N. America
                (4, 23),    # Holy Greatmartyr, Victorybearer and Wonderworker George
                (4, 25),    # Holy Apostle and Evangelist Mark
                (4, 30),    # Holy Apostle James, Brother of St John
        )
        for month, day in days:
            pdist = self.date_to_pdist(month, day, self.year)
            weekday = datetools.weekday_from_pdist(pdist)
            if -44 < pdist < -7 and weekday > Weekday.Monday:
                paremias[pdist] = False
                paremias[pdist-1] = True

        return paremias

    def date_to_pdist(self, month, day, year):
        dt = date(year, month, day)
        if self.use_julian:
            return datetools.julian_to_jdn(dt) - self.pascha
        else:
            return datetools.gregorian_to_jdn(dt) - self.pascha

    @cached_property
    def floats(self):
        """Return a dict of floating feast pdists and their indexes into the database."""

        floats = {
                self.fathers_six:               FloatIndex.FathersSix,
                self.fathers_seven:             FloatIndex.FathersSeventh,
                self.demetrius_saturday:        FloatIndex.DemetriusSaturday,
                self.synaxis_unmercenaries:     FloatIndex.SynaxisUnmercenaries,
                self.sun_before_elevation:      FloatIndex.SunBeforeElevation,
                self.sat_after_elevation:       FloatIndex.SatAfterElevation,
                self.sun_after_elevation:       FloatIndex.SunAfterElevation,
                self.forefathers:               FloatIndex.SunForefathers,
                self.sat_after_theophany:       FloatIndex.SatAfterTheophany,
                self.sun_after_theophany:       FloatIndex.SunAfterTheophany,
        }

        if self.sat_before_elevation == self.nativity_theotokos:
            # If the Saturday before the Elevation falls on the Nativity of the
            # Theotokos, we move its readings to the eve of the Elevation.
            floats[self.elevation - 1] = FloatIndex.SatBeforeElevationMoved
        else:
            floats[self.sat_before_elevation] = FloatIndex.SatBeforeElevation

        nativity_eve = self.nativity - 1
        if nativity_eve == self.sat_before_nativity:
            # Nativity is on Sunday; Royal Hours on Friday
            floats.update({
                self.nativity - 2:          FloatIndex.RoyalHoursNativityFriday,
                self.sun_before_nativity:   FloatIndex.SunBeforeNativity,
                nativity_eve:               FloatIndex.SatBeforeNativityEve,
            })
        elif nativity_eve == self.sun_before_nativity:
            # Nativity is on Monday; Royal Hours on Friday
            floats.update({
                self.nativity - 3:          FloatIndex.RoyalHoursNativityFriday,
                self.sat_before_nativity:   FloatIndex.SatBeforeNativity,
                nativity_eve:               FloatIndex.SunBeforeNativityEve,
            })
        else:
            floats.update({
                nativity_eve:               FloatIndex.EveNativity,
                self.sat_before_nativity:   FloatIndex.SatBeforeNativity,
                self.sun_before_nativity:   FloatIndex.SunBeforeNativity,
            })

        match datetools.weekday_from_pdist(self.nativity):
            case Weekday.Sunday:
                floats.update({
                    self.sat_after_nativity:    FloatIndex.SatAfterNativityBeforeTheophany,
                    self.nativity+1:            FloatIndex.SunAfterNativityMonday,
                    self.sun_before_theophany:  FloatIndex.SunBeforeTheophany,
                    self.theophany-1:           FloatIndex.TheophanyEve,
                })
            case Weekday.Monday:
                floats.update({
                    self.sat_after_nativity:    FloatIndex.SatAfterNativityBeforeTheophany,
                    self.sun_after_nativity:    FloatIndex.SunAfterNativitiy,
                    self.theophany-5:           FloatIndex.SatBeforeTheophanyJan,
                    self.theophany-1:           FloatIndex.TheophanyEve,
                })
            case Weekday.Tuesday:
                floats.update({
                    self.sat_after_nativity:    FloatIndex.SatAfterNativity,
                    self.sun_after_nativity:    FloatIndex.SunAfterNativitiy,
                    self.sat_before_theophany:  FloatIndex.SatBeforeTheophanyEve,
                    self.theophany-5:           FloatIndex.SatBeforeTheophanyJan,
                    self.theophany-2:           FloatIndex.RoyalHoursTheophanyFriday,
                })
            case Weekday.Wednesday:
                floats.update({
                    self.sat_after_nativity:    FloatIndex.SatAfterNativity,
                    self.sun_after_nativity:    FloatIndex.SunAfterNativitiy,
                    self.sat_before_theophany:  FloatIndex.SatBeforeTheophany,
                    self.sun_before_theophany:  FloatIndex.SunBeforeTheophanyEve,
                    self.theophany-3:           FloatIndex.RoyalHoursTheophanyFriday,
                })
            case Weekday.Thursday | Weekday.Friday:
                floats.update({
                    self.sat_after_nativity:    FloatIndex.SatAfterNativity,
                    self.sun_after_nativity:    FloatIndex.SunAfterNativitiy,
                    self.sat_before_theophany:  FloatIndex.SatBeforeTheophany,
                    self.sun_before_theophany:  FloatIndex.SunBeforeTheophany,
                    self.theophany-1:           FloatIndex.TheophanyEve,
                })
            case Weekday.Saturday:
                floats.update({
                    self.nativity+6:            FloatIndex.SatAfterNativityFriday,
                    self.sun_after_nativity:    FloatIndex.SunAfterNativitiy,
                    self.sat_before_theophany:  FloatIndex.SatBeforeTheophany,
                    self.sun_before_theophany:  FloatIndex.SunBeforeTheophany,
                    self.theophany-1:           FloatIndex.TheophanyEve,
                })

        # New Martyrs of Russia (OCA) is the Sunday on or before 1/31
        martyrs = self.date_to_pdist(1, 31, self.year)
        weekday = datetools.weekday_from_pdist(martyrs)
        if weekday != Weekday.Sunday:
            # The Sunday before 1/31
            martyrs = martyrs - 7 + ((7 - weekday) % 7)

        # TODO: replace numbers with FloatIndex enum

        floats[martyrs] = FloatIndex.NewMartyrsRussia

        # Floats around Annunciation
        match datetools.weekday_from_pdist(self.annunciation):
            case Weekday.Saturday:
                floats[self.annunciation-1]     = FloatIndex.AnnunciationParemFriday
                floats[self.annunciation]       = FloatIndex.AnnunciationSat
            case Weekday.Sunday:
                floats[self.annunciation]       = FloatIndex.AnnunciationSun
            case Weekday.Monday:
                floats[self.annunciation]       = FloatIndex.AnnunciationMon
            case _:
                floats[self.annunciation-1]     = FloatIndex.AnnunciationParemEve
                floats[self.annunciation]       = FloatIndex.AnnunciationWeekday

        return floats
