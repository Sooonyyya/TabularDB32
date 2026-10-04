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

class CharInvlType(BaseType):
    def normalize(self, value):
        value = self.text(value)
        if len(value) != 5 or value[0] != '[' or value[2] != ';' or value[4] != ']':
            raise ValidationError('Інтервал записують як [a;z], рівно два символи-межі.')
        lower, upper = value[1], value[3]
        if not scalar(lower) or not scalar(upper) or ord(lower) > ord(upper):
            raise ValidationError('Нижня межа інтервалу не може перевищувати верхню.')
        return value

class StringCharInvlType(BaseType):
    def __init__(self, lower, upper):
        if not scalar(lower) or not scalar(upper) or ord(lower) > ord(upper):
            raise ValidationError('Межі рядкового типу мають бути символами у правильному порядку.')
        self.lower, self.upper = lower, upper

    def normalize(self, value):
        value = self.text(value)
        if any(not ord(self.lower) <= ord(c) <= ord(self.upper) for c in value):
            raise ValidationError(f'Кожен символ має належати [{self.lower};{self.upper}].')
        return value

TYPE_NAMES = ('integer', 'real', 'char', 'string', 'charInvl', 'string(charInvl)')

def make_type(kind, lower=None, upper=None):
    types = dict(zip(TYPE_NAMES[:-1], [IntegerType, RealType, CharType, StringType, CharInvlType]))
    if kind == 'string(charInvl)':
        return StringCharInvlType(lower, upper)
    if kind not in types:
        raise ValidationError(f'Невідомий тип: {kind}.')
    if lower is not None or upper is not None:
        raise ValidationError('Межі схеми задають тільки для string(charInvl).')
    return types[kind]()
