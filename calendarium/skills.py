import logging

from datetime import datetime

from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.utils import get_slot_value, is_request_type, is_intent_name
from ask_sdk_model.ui import SimpleCard
from django.utils import timezone

from . import liturgics
from . import speech

logger = logging.getLogger(__name__)
skill_builder = SkillBuilder()

# These handlers don't seem to support async


def get_day(handler_input):
    if date_text := get_slot_value(handler_input, 'date'):
        date = datetime.strptime(date_text, '%Y-%m-%d')
        day = liturgics.Day(date.year, date.month, date.day)
    else:
        today = timezone.localtime()
        day = liturgics.Day(today.year, today.month, today.day)

    day.initialize()

    return day


class LaunchHandler(AbstractRequestHandler):
    """Handle intial launch of the skill.

    Give some basic information about today. Optionally continue on with
    scripture readings.
    """

    def can_handle(self, handler_input):
        return is_request_type('LaunchRequest')(handler_input)

    def handle(self, handler_input):
        builder = handler_input.response_builder

        logger.debug('Running OrthodoxDailyLaunchHandler.')

        today = timezone.localtime()
        day = liturgics.Day(today.year, today.month, today.day)
        day.initialize()

        speech_text, card_text = speech.day_speech(day)

        # Set speech
        speech_text += (
                f'<p>There are {len(day.readings)} scriptures readings.'
                f'Would you like to hear the readings?</p>'
        )
        builder.speak(speech_text)

        # Set card
        card = SimpleCard('About Today', card_text)
        builder.set_card(card)

        # Prepare for next step in the session
        build.set_should_end_session(False)
        session_attributes.original_intent = 'Launch'
        session_attributes.next_reading = 0
        session_attributes.date = timezone.localtime().strftime('%Y-%m-%d')

        return builder.response


class DayIntentHandler(AbstractRequestHandler):
    """Give some basic details about a specificly requested day."""

    def can_handle(self, handler_input):
        return is_intent_name('Day')(handler_input)

    def handle(self, handler_input):
        builder = handler_input.response_builder
        session_attributes = handler_input.attributes_manager.session_attributes

        logger.debug('Running DayIntentHander.')

        day = get_day(handler_input)

        # Set speech
        speech_text, card_text = speech.day_speech(day)
        builder.speak(speech_text)

        # Set card
        when = speech.when_speech(day)
        card = SimpleCard(f'About {when}', card_text)
        builder.set_card(card)

        # there are no further steps in this interaction
        build.set_should_end_session(True)

        return builder.response


class ScripturesIntentHandler(AbstractRequestHandler):
    """Build the initial scriptures Speech.

    We read the first reading on the initial Scriptures intent request and
    subsequent readings are triggered on AMAZON.YesIntent or
    AMAZON.NextIntent requests.
    """

    def can_handle(self, handler_input):
        return is_intent_name('Scriptures')(handler_input)

    def handle(self, handler_input):
        builder = handler_input.response_builder

        logger.debug('Running ScripturesIntentHander.')

        day = get_day(handler_input)

        # Build card

        date_text = day.gregorian_date.strftime('%A, %B %-d')
        card_text = f'Readings for {date_text}:\n\n'

        for reading in day.get_readings():
            card_text += f'{reading.display}\n'

        card = SimpleCard(f'About {when}', card_text)
        builder.set_card(card)

        # TODO: Build speech
        builder.speak('This is a test.')

        return builder.response


skill_builder.add_request_handler(LaunchHandler())
skill_builder.add_request_handler(DayIntentHandler())
skill_builder.add_request_handler(ScripturesIntentHandler())

orthodox_daily_skill = skill_builder.create()
