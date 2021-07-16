from calculate_anything.units.parser import PintDefinitionParser
import os

try:
    import pint
except ImportError:
    pint = None
from ..currency import CurrencyService
from ..lang import Language
from ..logging_wrapper import LoggingWrapper as logging
from ..utils import Singleton
from ..constants import MAIN_DIR, UNIT_ALIASES_RE

class UnitsService(metaclass=Singleton):
    MODE_NORMAL = 0
    MODE_CRAZY = 1

    def __init__(self):
        self._logger = logging.getLogger(__name__)
        self._unit_registry = None
        self._ctx = None
        self._base_currency = None
        self._enabled = False
        self._running = False
        self._unit_conversion_mode = UnitsService.MODE_CRAZY

    def _update_callback(self, data):
        self._logger.info('Updating currency registry')
        ureg = self._unit_registry
        ctx = self._ctx

        for currency, currency_info in data.items():
            if 'currency_' + currency not in ureg:
                ureg.define('currency_{} = nan currency_EUR'.format(currency))
                ureg.define('@alias currency_{0} = {0}'.format(currency))

            currency_units = ureg('currency_' + currency)
            if currency_units.units == self._base_currency.units:
                continue 
            rate = currency_info['rate']
            ctx.redefine('currency_{} = {} currency_EUR'.format(currency, 1 / rate))
        self._logger.info('Updated currency registry')
    
    def get_rate_timestamp(self, unit):
        if isinstance(unit, pint.Quantity):
            unit = unit.units
        unit_name = str(unit).replace('currency_', '')
        return CurrencyService().get_rate_timestamp(unit_name)

    def set_unit_conversion_mode(self, mode):
        self._unit_conversion_mode = mode

    @property
    def unit_conversion_mode(self):
        return self._unit_conversion_mode

    @property
    def base_currency(self):
        return self._base_currency

    @property
    def unit_registry(self):
        return self._unit_registry

    @property
    def enabled(self):
        return self._enabled

    @property
    def running(self):
        return self._running

    def enable(self):
        self._enabled = True
        return self

    def disable(self):
        self._enabled = False
        return self

    def stop(self):
        self._running = False
        self._unit_registry = None
        self._base_currency = None
        CurrencyService().remove_update_callback(self._update_callback)
        return self

    def run(self, force=False):
        if pint is None:
            return
        if force: pass
        elif self._running:
            return

        self._unit_registry = pint.UnitRegistry(
            autoconvert_offset_to_baseunit=True,
            case_sensitive=False
        )
        self._unit_registry.define('UNIT_SERVICE_NONE = [unit_service_none]')
        self._ctx = pint.Context('currency')
        self._unit_registry.add_context(self._ctx)

        pint_parser = PintDefinitionParser(self._unit_registry)
        pint_parser.load_file(os.path.join(MAIN_DIR, 'data/currency/definitions.txt'), translation_mode='units', is_currency=True)
        pint_parser.load_file(os.path.join(MAIN_DIR, 'data/lang/currency.txt'), translation_mode='units', is_currency=True)
        pint_parser.load_file(os.path.join(MAIN_DIR, 'data/lang/units.txt'), translation_mode='units', is_currency=False)
        self._base_currency = self._unit_registry.Quantity(1, 'currency_EUR')
        CurrencyService().remove_update_callback(self._update_callback)
        CurrencyService().add_update_callback(self._update_callback)
        self._running = True
        return self