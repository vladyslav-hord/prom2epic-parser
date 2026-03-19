# ""Unit conversion helpers.""

import re
import logging
from typing import Optional, Tuple


class UnitConverter:
    # ""Convert weight and distance units.""
    
    # Convert weight to grams.
    WEIGHT_CONVERSIONS = {
        'г': 1.0,
        'гр': 1.0,
        'грам': 1.0,
        'грамм': 1.0,
        'граммов': 1.0,
        'кг': 1000.0,
        'килограмм': 1000.0,
        'килограммов': 1000.0,
        'т': 1000000.0,
        'тонн': 1000000.0,
        'тонна': 1000000.0,
        'мг': 0.001,
        'миллиграмм': 0.001,
        'мг': 0.001,
        'lb': 453.592,
        'lbs': 453.592,
        'oz': 28.3495,
        'g': 1.0,
        'kg': 1000.0,
        'mg': 0.001,
    }
    
    # Convert distance to millimeters.
    DISTANCE_CONVERSIONS = {
        'мм': 1.0,
        'миллиметр': 1.0,
        'миллиметров': 1.0,
        'см': 10.0,
        'сантиметр': 10.0,
        'сантиметров': 10.0,
        'м': 1000.0,
        'метр': 1000.0,
        'метров': 1000.0,
        'км': 1000000.0,
        'километр': 1000000.0,
        'километров': 1000000.0,
        'дюйм': 25.4,
        'дюймов': 25.4,
        'in': 25.4,
        '"': 25.4,
        'фут': 304.8,
        'футов': 304.8,
        'ft': 304.8,
        "'": 304.8,
        'м': 1000.0,
        'mm': 1.0,
        'cm': 10.0,
        'm': 1000.0,
    }
    
    def __init__(self):
        # ""Initialize unit converter.""
        logging.info("UnitConverter initialized")
    
    def _extract_number_and_unit(self, value: str) -> Optional[Tuple[float, str]]:
        # ""Extract numeric value and unit from a string.""
        if not value or not isinstance(value, str):
            return None
        
        value = value.strip()
        
        number_match = re.search(r'(\d+[.,]?\d*)', value.replace(',', '.'))
        if not number_match:
            return None
        
        try:
            number = float(number_match.group(1))
        except ValueError:
            return None
        
        unit_match = re.search(r'[а-яА-Яa-zA-Z]+', value[number_match.end():])
        if unit_match:
            unit = unit_match.group(0).lower()
        else:
            unit_match = re.search(r'[а-яА-Яa-zA-Z]+', value)
            if unit_match:
                unit = unit_match.group(0).lower()
            else:
                unit = ''
        
        return (number, unit)
    
    def convert_weight(self, value: str) -> Optional[float]:
        # ""Convert a weight string to grams.""
        parsed = self._extract_number_and_unit(value)
        if not parsed:
            return None
        
        number, unit = parsed
        
        # If unit is missing, assume grams.
        if not unit:
            return number
        
        for unit_key, multiplier in self.WEIGHT_CONVERSIONS.items():
            if unit.startswith(unit_key) or unit_key.startswith(unit):
                grams = number * multiplier
                logging.debug(f"Weight conversion: {value} -> {grams} g")
                return grams
        
        logging.warning(f"Unknown weight unit '{unit}', assuming grams")
        return number
    
    def convert_distance(self, value: str) -> Optional[float]:
        # ""Convert a distance string to millimeters.""
        parsed = self._extract_number_and_unit(value)
        if not parsed:
            return None
        
        number, unit = parsed
        
        # If unit is missing, assume millimeters.
        if not unit:
            return number
        
        for unit_key, multiplier in self.DISTANCE_CONVERSIONS.items():
            if unit.startswith(unit_key) or unit_key.startswith(unit):
                mm = number * multiplier
                logging.debug(f"Distance conversion: {value} -> {mm} mm")
                return mm
        
        logging.warning(f"Unknown distance unit '{unit}', assuming millimeters")
        return number
    
    def normalize_numeric_value(self, value: str, attr_type: str, attr_name: str = "") -> Optional[float]:
        # ""Normalize numeric value according to attribute context.""
        if not value:
            return None
        
        attr_name_lower = attr_name.lower()
        
        weight_keywords = ['вага', 'вес', 'маса', 'масса', 'weight', 'mass']
        if any(keyword in attr_name_lower for keyword in weight_keywords):
            return self.convert_weight(value)
        
        distance_keywords = ['ширина', 'высота', 'глубина', 'длина', 'размер', 
                           'width', 'height', 'depth', 'length', 'size',
                           'діаметр', 'радіус', 'diameter', 'radius']
        if any(keyword in attr_name_lower for keyword in distance_keywords):
            return self.convert_distance(value)
        
        number_match = re.search(r'(\d+[.,]?\d*)', str(value).replace(',', '.'))
        if number_match:
            try:
                return float(number_match.group(1))
            except ValueError:
                pass
        
        return None




