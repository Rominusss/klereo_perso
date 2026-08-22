"""Number platform for Klereo."""
import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import PARAM_TYPES
from .entity import KlereoEntity, setup_discovery

_LOGGER = logging.getLogger(__name__)


def _extract_numbers(coordinator, system_id, details):
    """Extract number entities from system details.

    Writable setpoints (PARAM_TYPES) can appear in different places
    depending on firmware/API version: current firmware exposes them under
    details["params"], while older payloads (and the Jeedom plugin this is
    ported from) expose them directly under details["RegulModes"]. We look
    in both places so the entity is created regardless of source.
    """
    items = []
    seen_keys: set[str] = set()
    for source in (details.get("params", {}), details.get("RegulModes", {})):
        for key in source:
            if key not in PARAM_TYPES or key in seen_keys:
                continue
            seen_keys.add(key)
            uid = f"{system_id}_number_{key}"
            items.append((uid, KlereoNumber(coordinator, system_id, key, source[key])))
    return items


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Klereo number entities."""
    setup_discovery(hass, entry, async_add_entities, _extract_numbers)


class KlereoNumber(KlereoEntity, NumberEntity):
    """Representation of a Klereo adjustable parameter."""

    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, system_id, key, initial_value):
        """Initialize the number entity."""
        super().__init__(coordinator, system_id)
        self._key = key
        self._param = PARAM_TYPES[key]

        self._attr_unique_id = f"{system_id}_number_{key}"
        self._attr_name = self._param["name"]
        self._attr_native_unit_of_measurement = self._param.get("unit")
        self._attr_native_step = self._param.get("step", 1)
        self._attr_native_value = initial_value
        self._update_bounds(coordinator.data.get(system_id, {}).get("details", {}))

    def _update_bounds(self, details):
        """Refresh min/max from the installation's actual configured bounds.

        Falls back to the static defaults in PARAM_TYPES when the
        installation doesn't expose min_key/max_key (e.g. ConsigneChlore).
        """
        params = details.get("params", {})
        min_key = self._param.get("min_key")
        max_key = self._param.get("max_key")
        self._attr_native_min_value = params.get(min_key, self._param.get("min", 0))
        self._attr_native_max_value = params.get(max_key, self._param.get("max", 100))

    @callback
    def _handle_coordinator_update(self):
        """Handle updated data from the coordinator."""
        if self.system_id not in self.coordinator.data:
            self._attr_available = False
            return super()._handle_coordinator_update()
        self._attr_available = True
        details = self.coordinator.data[self.system_id].get("details", {})
        self._update_bounds(details)
        # Current firmware exposes setpoints under "params"; older payloads
        # expose them directly under "RegulModes". Check both.
        params = details.get("params", {})
        regul = details.get("RegulModes", {})
        if self._key in params:
            self._attr_native_value = params[self._key]
        elif self._key in regul:
            self._attr_native_value = regul[self._key]
        super()._handle_coordinator_update()

    async def async_set_native_value(self, value: float) -> None:
        """Set the parameter value."""
        self._attr_native_value = value
        self.async_write_ha_state()
        await self.coordinator.async_set_param(self.system_id, self._key, value)
