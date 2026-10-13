from abc import ABC, abstractmethod
import math
import re


class ValidationError(ValueError):
    pass


def scalar(value):
    return isinstance(value, str) and len(value) == 1 and not 0xD800 <= ord(value) <= 0xDFFF


class BaseType(ABC):
    @abstractmethod
    def normalize(self, value: str) -> str:
        pass

    def validation(self, value: str) -> bool:
        try:
            self.normalize(value)
            return True
        except ValidationError:
            return False

    def text(self, value):
        if not isinstance(value, str):
            raise ValidationError('Значення комірки має бути рядком.')
        if any(0xD800 <= ord(c) <= 0xDFFF for c in value):
            raise ValidationError('Недопустимий символ Unicode.')
        return value


class IntegerType(BaseType):
    def normalize(self, value):
        value = self.text(value).strip()
        if not re.fullmatch(r'[+-]?[0-9]+', value):
            raise ValidationError('Очікується ціле число, наприклад -12.')
        sign = '-' if value.startswith('-') else ''
        digits = value.lstrip('+-').lstrip('0') or '0'
        return sign + digits if digits != '0' else '0'


class RealType(BaseType):
    def normalize(self, value):
        value = self.text(value).strip()
        if not re.fullmatch(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?', value):
            raise ValidationError('Очікується дійсне число з крапкою, наприклад 2.5.')
        number = float(value)
        if not math.isfinite(number):
            raise ValidationError('Число має бути скінченним і в межах real.')
        return repr(number if number != 0 else 0.0)


class CharType(BaseType):
    def normalize(self, value):
        value = self.text(value)
        if not scalar(value):
            raise ValidationError('char має містити рівно один символ Unicode.')
        return value


class StringType(BaseType):
    def normalize(self, value):
        return self.text(value)


class _IntervalMixin:
    def __init__(self, lower, upper):
        if not scalar(lower) or not scalar(upper):
            raise ValidationError('Межі інтервалу мають містити рівно по одному символу.')
        if ord(lower) > ord(upper):
            raise ValidationError('Нижня межа інтервалу не може перевищувати верхню.')
        self.lower = lower
        self.upper = upper

    def in_interval(self, char):
        return ord(self.lower) <= ord(char) <= ord(self.upper)


class CharInvlType(_IntervalMixin, BaseType):
    """Один символ, що належить заданому в схемі замкненому інтервалу."""
    def normalize(self, value):
        value = self.text(value)
        if not scalar(value):
            raise ValidationError('charInvl має містити рівно один символ Unicode.')
        if not self.in_interval(value):
            raise ValidationError(f'Символ має належати інтервалу [{self.lower};{self.upper}].')
        return value


class StringCharInvlType(_IntervalMixin, BaseType):
    """Рядок, кожен символ якого належить заданому в схемі інтервалу."""
    def normalize(self, value):
        value = self.text(value)
        if any(not self.in_interval(c) for c in value):
            raise ValidationError(f'Кожен символ має належати інтервалу [{self.lower};{self.upper}].')
        return value


TYPE_NAMES = ('integer', 'real', 'char', 'string', 'charInvl', 'string(charInvl)')
INTERVAL_TYPES = ('charInvl', 'string(charInvl)')


def make_type(kind, lower=None, upper=None):
    if kind == 'charInvl':
        return CharInvlType(lower, upper)
    if kind == 'string(charInvl)':
        return StringCharInvlType(lower, upper)

    types = {
        'integer': IntegerType,
        'real': RealType,
        'char': CharType,
        'string': StringType,
    }
    if kind not in types:
        raise ValidationError(f'Невідомий тип: {kind}.')
    if lower is not None or upper is not None:
        raise ValidationError('Межі задають тільки для charInvl та string(charInvl).')
    return types[kind]()
