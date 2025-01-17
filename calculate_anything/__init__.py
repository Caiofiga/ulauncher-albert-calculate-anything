# -*- coding: utf-8 -*-
# Copyright (c) 2017 Benedict Dudel
# Copyright (c) 2023 Max
# Copyright (c) 2023 Pete-Hamlin
#
# Adapted for "Calculate Anything" in the style of the "Pass" plugin script.
# Original "Calculate Anything" by @tchar
#
# This plugin provides currency, units, date/time conversions, base conversions
# and general calculator functionality within Albert.

import os
import sys
from albert import (
    PluginInstance,
    TriggerQueryHandler,
    StandardItem,
    Action,
    runDetachedProcess,
    setClipboardText,
)

# Plugin metadata
md_iid = "2.0"
md_version = "0.1"
md_name = "Calculate Anything"
md_description = (
    "A ULauncher/Albert extension that supports currency, units and date/time "
    "conversion, as well as a calculator that supports complex numbers and functions."
)
md_license = "MIT"
md_url = "https://github.com/tchar/ulauncher-albert-calculate-anything"
md_authors = ["@tchar"]
md_bin_dependencies = []

################################### SETTINGS #######################################
# The following defaults can be changed via the plugin's configWidget or by editing
# the below lines directly.

# Currency provider: one of ("internal", "fixerio")
DEFAULT_CURRENCY_PROVIDER = "internal"
# API key (for fixer.io or similar)
DEFAULT_API_KEY = ""
# Cache update interval (defaults to one day = 86400 seconds)
DEFAULT_CACHE = 86400
# Default currencies to show if no target is provided
DEFAULT_CURRENCIES = "USD,EUR,GBP,CAD"
# Default cities to show when converting timezones
DEFAULT_CITIES = "New York City US, London GB, Madrid ES, Vancouver CA, Athens GR"
# Units conversion mode ("normal" or "crazy")
DEFAULT_UNITS_MODE = "normal"
# Show placeholder if query is empty
DEFAULT_SHOW_EMPTY_PLACEHOLDER = False
# Triggers (keywords that activate this extension)
DEFAULT_TRIGGERS = ["=", "time", "dec", "bin", "hex", "oct"]
####################################################################################

try:
    from calculate_anything.constants import MAIN_DIR
except ImportError:
    MAIN_DIR = os.path.dirname(os.path.realpath(__file__))
    sys.path.append(MAIN_DIR)

from calculate_anything import logging
from calculate_anything.preferences import Preferences
from calculate_anything.lang import LanguageService
from calculate_anything.query.handlers import (
    MultiHandler,
    UnitsQueryHandler,
    CalculatorQueryHandler,
    PercentagesQueryHandler,
    TimeQueryHandler,
    Base10QueryHandler,
    Base2QueryHandler,
    Base8QueryHandler,
    Base16QueryHandler,
)
from calculate_anything.utils import images_dir

def initialize_preferences(
    currency_provider: str,
    api_key: str,
    cache_interval: int,
    default_currencies: str,
    default_cities: str,
    units_mode: str
):
    """
    Helper function to set up Calculate Anything preferences and providers.
    """
    preferences = Preferences()
    preferences.language.set("en_US")
    preferences.currency.add_provider(currency_provider.lower(), api_key or "")
    preferences.currency.set_cache_update_frequency(cache_interval)
    preferences.currency.set_default_currencies(default_currencies)
    preferences.units.set_conversion_mode(units_mode)
    preferences.time.set_default_cities(default_cities)
    preferences.commit()

class Plugin(PluginInstance, TriggerQueryHandler):
    def __init__(self):
        # Initialize plugin
        PluginInstance.__init__(self)
        TriggerQueryHandler.__init__(
            self,
            self.id,
            self.name,
            self.description,
            synopsis="<expression>",
            # Use the first trigger by default. You can change this to your liking.
            # e.g., if you want the plugin to trigger with "calc ", set defaultTrigger="calc ".
            defaultTrigger=DEFAULT_TRIGGERS[0] + " "
        )

        # Icon used in results
        self.iconUrls = [os.path.join(MAIN_DIR, images_dir("icon.svg"))]

        # Read configuration or use defaults
        self._currencyProvider = self.readConfig("currency_provider", str) or DEFAULT_CURRENCY_PROVIDER
        self._apiKey = self.readConfig("api_key", str) or DEFAULT_API_KEY
        self._cache = self.readConfig("cache", int) or DEFAULT_CACHE
        self._defaultCurrencies = self.readConfig("default_currencies", str) or DEFAULT_CURRENCIES
        self._defaultCities = self.readConfig("default_cities", str) or DEFAULT_CITIES
        self._unitsMode = self.readConfig("units_mode", str) or DEFAULT_UNITS_MODE
        self._showEmptyPlaceholder = (
            self.readConfig("show_empty_placeholder", bool) or DEFAULT_SHOW_EMPTY_PLACEHOLDER
        )

        # For convenience, store triggers in a property
        stored_triggers = self.readConfig("triggers", str)
        if stored_triggers:
            self._triggers = [tr.strip() for tr in stored_triggers.split(",")]
        else:
            self._triggers = DEFAULT_TRIGGERS

        # Initialize the "Calculate Anything" core preferences
        initialize_preferences(
            self._currencyProvider,
            self._apiKey,
            self._cache,
            self._defaultCurrencies,
            self._defaultCities,
            self._unitsMode
        )

    #
    # Properties allow reading/writing config from a single place
    #
    @property
    def currencyProvider(self) -> str:
        return self._currencyProvider

    @currencyProvider.setter
    def currencyProvider(self, value: str):
        self._currencyProvider = value
        self.writeConfig("currency_provider", value)

    @property
    def apiKey(self) -> str:
        return self._apiKey

    @apiKey.setter
    def apiKey(self, value: str):
        self._apiKey = value
        self.writeConfig("api_key", value)

    @property
    def cache(self) -> int:
        return self._cache

    @cache.setter
    def cache(self, value: int):
        self._cache = value
        self.writeConfig("cache", value)

    @property
    def defaultCurrencies(self) -> str:
        return self._defaultCurrencies

    @defaultCurrencies.setter
    def defaultCurrencies(self, value: str):
        self._defaultCurrencies = value
        self.writeConfig("default_currencies", value)

    @property
    def defaultCities(self) -> str:
        return self._defaultCities

    @defaultCities.setter
    def defaultCities(self, value: str):
        self._defaultCities = value
        self.writeConfig("default_cities", value)

    @property
    def unitsMode(self) -> str:
        return self._unitsMode

    @unitsMode.setter
    def unitsMode(self, value: str):
        self._unitsMode = value
        self.writeConfig("units_mode", value)

    @property
    def showEmptyPlaceholder(self) -> bool:
        return self._showEmptyPlaceholder

    @showEmptyPlaceholder.setter
    def showEmptyPlaceholder(self, value: bool):
        self._showEmptyPlaceholder = value
        self.writeConfig("show_empty_placeholder", value)

    @property
    def triggers(self) -> list:
        return self._triggers

    @triggers.setter
    def triggers(self, value: list):
        self._triggers = value
        self.writeConfig("triggers", ",".join(value))

    #
    # Provide a config widget so users can modify settings via the Albert UI
    #
    def configWidget(self):
        return [
            {
                "type": "groupbox",
                "title": "Currency & Units Settings",
                "children": [
                    {
                        "type": "lineedit",
                        "property": "currencyProvider",
                        "label": "Currency Provider (internal or fixerio)",
                    },
                    {
                        "type": "lineedit",
                        "property": "apiKey",
                        "label": "API Key (for fixer.io or similar)",
                    },
                    {
                        "type": "spinbox",
                        "property": "cache",
                        "label": "Cache Update Interval (seconds)",
                        "widget_properties": {"min": 0, "max": 604800},  # up to 7 days
                    },
                    {
                        "type": "lineedit",
                        "property": "defaultCurrencies",
                        "label": "Default Currencies",
                    },
                    {
                        "type": "lineedit",
                        "property": "defaultCities",
                        "label": "Default Cities for Timezones",
                    },
                    {
                        "type": "lineedit",
                        "property": "unitsMode",
                        "label": "Units Conversion Mode (normal or crazy)",
                    },
                ],
            },
            {
                "type": "groupbox",
                "title": "Plugin Behavior",
                "children": [
                    {
                        "type": "checkbox",
                        "property": "showEmptyPlaceholder",
                        "label": "Show placeholder if no query?",
                    },
                    {
                        "type": "lineedit",
                        "property": "triggers",
                        "label": "Triggers (comma-separated, e.g., =, time, dec, bin, hex, oct)",
                        "widget_properties": {
                            "placeholderText": "Enter triggers separated by commas"
                        },
                    },
                ],
            },
        ]

    #
    # The main entry point for queries
    #
    def handleTriggerQuery(self, query):
        # Because we set defaultTrigger to the first item in our triggers list,
        # the user typed something like "= 2+2" or "time 16:00" etc.

        # We'll parse out which trigger (if any) matches what the user typed
        user_input = query.string.strip()

        # If user input is empty and we're not forced to show placeholders, return
        if not user_input and not self.showEmptyPlaceholder:
            return

        # We'll call a function that tries each trigger. If none matches, we just
        # check if we have no triggers at all, and handle accordingly.
        results = self.getCalculateAnythingResults(user_input)
        if results:
            query.add(results)

    #
    # Adapted from the original "handleGlobalQuery" in your script
    #
    def getCalculateAnythingResults(self, user_input):
        """
        Return a list of StandardItems based on user_input, applying the logic
        for each recognized trigger (calculator, time, base conversions, etc.).
        """
        # If there are no triggers, we use the standard "calculator" approach
        if not self.triggers:
            return self.buildResults(user_input, calculator_only=True)

        # Try each recognized trigger in our list, in the order we have them:
        # 0: '='
        # 1: 'time'
        # 2: 'dec'
        # 3: 'bin'
        # 4: 'hex'
        # 5: 'oct'
        # We'll parse them the same way the original script did.
        for idx, trigger in enumerate(self.triggers):
            # Ensure we have a trailing space. Example: "hex "
            trigger_with_space = trigger + " "
            if user_input.startswith(trigger_with_space):
                query_nokw = user_input[len(trigger_with_space) :].strip()
                return self.buildResults(query_nokw, trigger_mode=trigger.lower())

        # If it doesn't match any known triggers but we do have triggers,
        # just return an empty list or a placeholder if configured.
        if self.showEmptyPlaceholder:
            return self.buildPlaceholder("calculator", "")
        return []

    def buildResults(self, query_string, calculator_only=False, trigger_mode=None):
        """
        Using the logic from the original script, build a list of StandardItems.
        """
        # If we're ignoring triggers, we handle everything with the calculator handlers
        if calculator_only:
            handlers = [UnitsQueryHandler, CalculatorQueryHandler, PercentagesQueryHandler]
            query_str = CalculatorQueryHandler().keyword + " " + query_string
            mode = "calculator"
        else:
            # Dispatch to the relevant handlers based on trigger_mode
            if trigger_mode == "time":
                query_str = TimeQueryHandler().keyword + " " + query_string
                handlers = [TimeQueryHandler]
                mode = "time"
            elif trigger_mode == "dec":
                query_str = Base10QueryHandler().keyword + " " + query_string
                handlers = [Base10QueryHandler]
                mode = "dec"
            elif trigger_mode == "hex":
                query_str = Base16QueryHandler().keyword + " " + query_string
                handlers = [Base16QueryHandler]
                mode = "hex"
            elif trigger_mode == "oct":
                query_str = Base8QueryHandler().keyword + " " + query_string
                handlers = [Base8QueryHandler]
                mode = "oct"
            elif trigger_mode == "bin":
                query_str = Base2QueryHandler().keyword + " " + query_string
                handlers = [Base2QueryHandler]
                mode = "bin"
            else:
                # Default is calculator
                query_str = CalculatorQueryHandler().keyword + " " + query_string
                handlers = [UnitsQueryHandler, CalculatorQueryHandler, PercentagesQueryHandler]
                mode = "calculator"

        # Actually run the MultiHandler for the user input
        mh = MultiHandler()
        results = mh.handle(query_str, *handlers)

        items = []
        for idx, result in enumerate(results):
            icon_path = result.icon or images_dir("icon.svg")
            icon_path = os.path.join(MAIN_DIR, icon_path)

            actions = []
            if result.clipboard is not None:
                actions.append(
                    Action(
                        "clipboard",
                        "Copy to clipboard",
                        lambda c=result.clipboard: setClipboardText(c),
                    )
                )

            items.append(
                StandardItem(
                    id=f"{md_name}_{idx}",
                    text=result.name,
                    subtext=result.description,
                    iconUrls=[icon_path],
                    actions=actions,
                )
            )

        # If no items and we need to show a placeholder, build it
        if not items and (query_string.strip() == "" or self.showEmptyPlaceholder):
            items = self.buildPlaceholder(mode, query_string)

        return items

    def buildPlaceholder(self, mode, query_string):
        """
        Build a "no results" placeholder item, localized if possible.
        """
        icon_path = os.path.join(MAIN_DIR, images_dir("icon.svg"))
        no_result_text = LanguageService().translate("no-result", "misc")
        no_result_sub = LanguageService().translate(f"no-result-{mode}-description", "misc")

        return [
            StandardItem(
                id="calculate_anything_no_result",
                text=no_result_text,
                subtext=no_result_sub,
                iconUrls=[icon_path],
            )
        ]
