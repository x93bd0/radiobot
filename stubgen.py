from typing import (
  Dict, Any, Type, List,
  Tuple, Set, Optional,
  ForwardRef, get_args
)

from dataclasses import dataclass
import re


@dataclass
class ClassRoot:
  code: str
  depends: List[str]


class StubGenerator:
  def __init__(self):
    self.definitions: Dict[str, ClassRoot] = {}
    self.imports: Set[str] = set(['typing'])

  def generate_root(self, root: Dict[str, Any], first: bool = True) -> None:
    name: Optional[str]
    if not first:
      name = root.pop('__name__')

    requires: List[str] = []
    output: List[str] = []

    for key, sroot in root.items():
      if isinstance(sroot, dict):
        self.generate_root(sroot, False)
        continue
      
      output.append(self.generate_param(
          key, sroot, requires))

    if not first:
      self.definitions[name] = ClassRoot(
        '\n'.join(output), requires)

  def _genparam_routine(self, params: List[str | Type], requires: List[str]):
    for param in params:
      if isinstance(param, List | Tuple):
        self._genparam_routine(param, requires)
        continue

      if isinstance(param, ForwardRef):
        param = param.__forward_arg__
      
      if isinstance(param, str):
        requires.append(param)
        continue

      if str(param).startswith('typing.'):
        self._genparam_routine(get_args(param), requires)
        continue

      if hasattr(param, '__module__'):
        self.imports.add(param.__module__)

  def generate_param(
    self, key: str, param: str | Type | ForwardRef,
    requires: List[str]
  ) -> str:
    if isinstance(param, ForwardRef):
      param = param.__forward_arg__

    if isinstance(param, str):
      requires.append(param)
      return f'{key}: {param}'

    if str(param).startswith('<'):
      return f'{key}: {param.__name__}'

    if str(param).startswith('typing.'):
      self._genparam_routine(get_args(param), requires)

    else:
      self.imports.add(param)

    return f'{key}: {param}'

  def _tocode_routine(
    self, name: str, defi: ClassRoot, code: List[str],
    imported: List[str], importing: List[str]
  ) -> str:
    importing.append(name)
    for dep in defi.depends:
      if dep in imported:
        continue

      if dep in importing:
        raise Exception(
          'Cyclical reference detected when generating stub`s')
      
      self._tocode_routine(
        dep, self.definitions[dep],
        code, imported, importing)

    code.append(f'class {name}:\n\t{"\n\t".join(defi.code.split("\n"))}')
    importing.remove(name)
    imported.append(name)

  def to_code(self) -> str:
    code: List[str] = []
    imported: List[str] = []
    importing: List[str] = []

    for k, defi in self.definitions.items():
      if k not in imported:
        self._tocode_routine(
          k, defi, code,
          imported, importing)

    out: str
    if not self.imports:
      out = '\n\n'.join(code) + '\n'

    else:
      out = '\n'.join([f'import {x}' for x in self.imports]) + \
        '\n\n' + '\n\n'.join(code) + '\n'

    m: re.Match = re.search(r'ForwardRef\(\'\w*\'\)', out)
    while m:
      sp = m.span()
      out = out[:sp[0]] + out[sp[0] + 12:sp[1] - 2] + out[sp[1]:]
      m = re.search(r'ForwardRef\(\'\w*\'\)', out)

    return out


def generate(root: Dict[str, Any]) -> str:
  stub: StubGenerator = StubGenerator()
  stub.generate_root(root)
  return stub.to_code().replace('NoneType', 'None')
