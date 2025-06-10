from antlr4 import *
from antlr4.error.ErrorListener import ErrorListener
from PySQLLexer import PySQLLexer
from PySQLParser import PySQLParser
from PySQLVisitor import PySQLVisitor
import os
import difflib
from antlr4.error.Errors import (
    LexerNoViableAltException,
    InputMismatchException,    
    NoViableAltException,      
    FailedPredicateException,  
    RecognitionException       
)
import re


def get_closest_match(name, candidates, cutoff=0.6, n=1):
    """Znajduje najbliższe dopasowania dla 'name' w liście 'candidates'."""
    matches = difflib.get_close_matches(name, candidates, n=n, cutoff=cutoff)
    if matches:
        if len(matches) == 1:
            return f"Did you mean '{matches[0]}'?"
        else:
            return f"Did you mean one of: {', '.join(f'{m}' for m in matches)}?"
    return None

# Exception to unwind stack on return
class ReturnException(Exception):
    def __init__(self, value):
        self.value = value

# Dodaj te definicje na początku pliku lub w osobnym module
class PySQLException(Exception):
    def __init__(self, message, line=None, column=None, context_text=None, suggestion=None):
        super().__init__(message)
        self.message = message
        self.line = line
        self.column = column
        self.context_text = context_text # Tekst tokenu/reguły, która spowodowała błąd
        self.suggestion = suggestion     # Sugestia (np. "Did you mean 'length'?")

    def __str__(self):
        error_msg = f"{self.__class__.__name__}: {self.message}"
        if self.line is not None:
            error_msg += f" at line {self.line}"
            if self.column is not None:
                error_msg += f":{self.column}"
        if self.context_text:
            error_msg += f" (near '{self.context_text}')"
        if self.suggestion:
            error_msg += f". {self.suggestion}"
        return error_msg

class PySQLSyntaxError(PySQLException): # Dziedziczy z PySQLException
    def __str__(self):
        # Zaczynamy od nazwy klasy i głównego komunikatu
        error_msg = f"{self.__class__.__name__}: {self.message}"

        # Dodajemy informację o linii, jeśli jest dostępna
        if self.line is not None:
            error_msg += f" at line {self.line}"
        # CELOWO POMIJAMY INFORMACJĘ O KOLUMNIE dla PySQLSyntaxError

        # Dodajemy tekst kontekstowy, jeśli jest dostępny (tak jak w klasie bazowej)
        if self.context_text:
            error_msg += f" (near '{self.context_text}')"

        # Dodajemy sugestię, jeśli jest dostępna (tak jak w klasie bazowej)
        # Zakładamy, że self.suggestion jest atrybutem z klasy bazowej
        if self.suggestion:
            error_msg += f". {self.suggestion}"
            
        return error_msg
class PySQLNameError(PySQLException):
    def __str__(self):
        error_msg = f"{self.__class__.__name__}: {self.message}"
        if self.line is not None:
            error_msg += f" at line {self.line}"
            if self.column is not None:
                error_msg += f":{self.column}"
        
        # Sprawdź, czy context_text nie jest po prostu powtórzeniem nazwy z message
        # To jest uproszczone założenie, możesz potrzebować bardziej
        # zaawansowanej logiki, aby uniknąć redundancji.
        # Na przykład, jeśli message zawsze zawiera nazwę w cudzysłowach.
        if self.context_text and self.context_text not in self.message:
             error_msg += f" (near '{self.context_text}')"
        
        if self.suggestion:
            error_msg += f". {self.suggestion}"
        return error_msg
class PySQLTypeError(PySQLException): pass
class PySQLValueError(PySQLException): pass   # Np. dzielenie przez zero, błędy konwersji
class PySQLImportError(PySQLException): pass
class PySQLRuntimeError(PySQLException): pass  # Ogólne błędy wykonania

class PySQLInterpreter(PySQLVisitor):
    def __init__(self, base_dir="", shared_import_context=None):
        self.scopes = [{}]  # Stos zakresów zmiennych
        self.var_types = [{}]  # Typy zmiennych dla każdego scope
        self.functions = {}
        self.base_dir = base_dir
        self.functions = {
            # String functions
            'toUpper': ([('s', 'string')], 'string', self.builtin_toUpper),
            'toLower': ([('s', 'string')], 'string', self.builtin_toLower),
            'startsWith': ([('s', 'string'), ('prefix', 'string')], 'bool', self.builtin_startsWith),
            'endsWith': ([('s', 'string'), ('suffix', 'string')], 'bool', self.builtin_endsWith),
            'contains': ([('s', 'string'), ('substring', 'string')], 'bool', self.builtin_contains),
            
            # Numerical aggregations
            'sum': ([('arr', 'array<mixed>')], 'mixed', self.builtin_sum),
            'avg': ([('arr', 'array<mixed>')], 'float', self.builtin_avg),
            'min': ([('arr', 'array<mixed>')], 'mixed', self.builtin_min),
            'max': ([('arr', 'array<mixed>')], 'mixed', self.builtin_max),
            'count': ([('arr', 'array<mixed>')], 'int', self.builtin_count),
            'median': ([('arr', 'array<mixed>')], 'float', self.builtin_median),
            
            # Array functions
            'len': ([('arr', 'mixed')], 'int', self.builtin_length),  # Array version
            
            # Type function
            'type': ([('value', 'mixed')], 'string', self.builtin_type)
        }

        if shared_import_context is None:
            self.shared_import_context = {
                'globally_parsed_modules': {}, # file_path -> {'scopes':..., 'functions':..., 'var_types':...}
                'currently_parsing': set()     # set of absolute file_paths
            }
        else:
            self.shared_import_context = shared_import_context


           
    def _get_or_parse_module(self, relative_path):
        file_path_to_import = os.path.abspath(os.path.join(self.base_dir, relative_path))

        if file_path_to_import in self.shared_import_context['globally_parsed_modules']:
            return self.shared_import_context['globally_parsed_modules'][file_path_to_import]

        if file_path_to_import in self.shared_import_context['currently_parsing']:
            raise Exception(f"Circular import detected: File {file_path_to_import} is already being parsed.")

        self.shared_import_context['currently_parsing'].add(file_path_to_import)

        if not os.path.exists(file_path_to_import):
            self.shared_import_context['currently_parsing'].remove(file_path_to_import)
            raise Exception(f"Import file not found: {file_path_to_import}")

        with open(file_path_to_import, 'r', encoding='utf-8') as f:
            imported_code = f.read()

        lexer = PySQLLexer(InputStream(imported_code))
        stream = CommonTokenStream(lexer)
        parser = PySQLParser(stream)

        error_listener = PySQLErrorListener() # Assuming PySQLErrorListener is defined
        lexer.removeErrorListeners()
        lexer.addErrorListener(error_listener)
        parser.removeErrorListeners()
        parser.addErrorListener(error_listener)

        tree = parser.prog()

        module_interpreter = PySQLInterpreter(
            base_dir=os.path.dirname(file_path_to_import),
            shared_import_context=self.shared_import_context 
        )

        try:
            module_interpreter.visit(tree) # This populates module_interpreter's state
        except Exception as e:
            self.shared_import_context['currently_parsing'].remove(file_path_to_import)
            raise Exception(f"Error while parsing imported file '{file_path_to_import}': {str(e)}")


        module_state = {
            'scopes': module_interpreter.scopes.copy(),  # ZAMIANA memory -> scopes
            'functions': module_interpreter.functions.copy(),
            'var_types': module_interpreter.var_types.copy()
        }


        self.shared_import_context['globally_parsed_modules'][file_path_to_import] = {
            'scopes': module_interpreter.scopes.copy(),
            'functions': module_interpreter.functions.copy(),
            'var_types': module_interpreter.var_types.copy()
}

        self.shared_import_context['currently_parsing'].remove(file_path_to_import)

        return module_state
    
    def visitFullImport(self, ctx: PySQLParser.FullImportContext):
        path_raw = ctx.STRING().getText()[1:-1]  # Pobranie nazwy pliku

        module_state = self._get_or_parse_module(path_raw)

        # Importowanie zmiennych z modułu do aktualnego scope'a
        for name, value in module_state['scopes'][0].items():  # ZAMIANA memory -> scopes[0]
            if name in self.functions:  # Sprawdzenie konfliktu nazw z funkcją
                raise Exception(f"Name clash during full import from '{path_raw}': Cannot import variable '{name}', a function with this name already exists in the current scope.")
            self.scopes[-1][name] = value  # ZAMIANA memory -> scopes[-1]
            
            if name in module_state['var_types']:  # Tak samo kopiujemy typy
                self.var_types[-1][name] = module_state['var_types'][name]  # ZAMIANA var_types

        # Importowanie funkcji
        for name, func_def in module_state['functions'].items():
            if name in self.scopes[-1]:  # Sprawdzenie konfliktu nazw z zmienną
                raise Exception(f"Name clash during full import from '{path_raw}': Cannot import function '{name}', a variable with this name already exists in the current scope.")
            self.functions[name] = func_def  # Funkcje pozostają globalne

        return None

    
    def visitSelectiveImport(self, ctx: PySQLParser.SelectiveImportContext):  
        path_raw = ctx.STRING().getText()[1:-1]  # Pobranie nazwy pliku

        items_to_import = [id_node.getText() for id_node in ctx.idList().identifierName()]
        module_state = self._get_or_parse_module(path_raw)

        for item_name in items_to_import:
            imported_successfully = False

            # Importowanie zmiennych z modułu do aktualnego scope'a
            if item_name in module_state['scopes'][0]:  # ZAMIANA memory -> scopes[0]
                if item_name in self.functions:  # Sprawdzenie konfliktu nazw z funkcją
                    raise Exception(f"Name clash while importing '{item_name}' from '{path_raw}': A function with this name already exists in the current scope.")
                self.scopes[-1][item_name] = module_state['scopes'][0][item_name]  # ZAMIANA memory -> scopes[-1]

                if item_name in module_state['var_types']:  # Kopiowanie typów zmiennych
                    self.var_types[-1][item_name] = module_state['var_types'][item_name]  # ZAMIANA var_types

                imported_successfully = True

            # Importowanie funkcji
            if item_name in module_state['functions']:
                if not imported_successfully:  # Jeśli jeszcze nie zostało zaimportowane jako zmienna
                    if item_name in self.scopes[-1]:  # Sprawdzenie konfliktu nazw z zmienną
                        raise Exception(f"Name clash while importing function '{item_name}' from '{path_raw}': A variable with this name already exists in the current scope.")
                    self.functions[item_name] = module_state['functions'][item_name]
                    imported_successfully = True

            # Sprawdzenie, czy import się udał
            if not imported_successfully:
                raise Exception(f"Item '{item_name}' not found as variable or function in module '{path_raw}' (imported at line {ctx.start.line})")

        return None

    
    def visitFuncDef(self, ctx):
        name = ctx.identifierName().getText()
        line = ctx.start.line

        # Walidacja nazwy funkcji
        if not re.match(r'^[a-zA-Z_][a-zA-Z_0-9]*$', name):
            raise PySQLNameError(f"Invalid function name", line=line, context_text=name)

        if name in self.functions:
            raise PySQLNameError(f"Function '{name}' already defined", line=line, context_text=name)

        params = []
        if ctx.paramList():
            param_names_ctx = ctx.paramList().identifierName()
            param_types_ctx = ctx.paramList().varType()

            for pname_ctx, ptype_ctx in zip(param_names_ctx, param_types_ctx):
                param_name = pname_ctx.getText()

                if not re.match(r'^[a-zA-Z_][a-zA-Z_0-9]*$', param_name):
                    raise PySQLNameError(f"Invalid parameter name", line=pname_ctx.start.line, context_text=param_name)

                if param_name in [p[0] for p in params]:
                    raise PySQLNameError(f"Duplicate parameter name '{param_name}' in function definition", line=pname_ctx.start.line, context_text=param_name)

                params.append((param_name, ptype_ctx.getText()))

        ret_type = ctx.returnType().getText()
        body = ctx.stat()

        # Tworzenie funkcji jako obiektu wywoływalnego
        def function_wrapper(*args):
            self.scopes.append({})  # Tworzymy nowy lokalny zakres dla funkcji
            self.var_types.append({})  # Tworzymy nowy lokalny zakres typów

            # Przypisanie parametrów do lokalnego scope'a funkcji
            for (param_name, param_type), arg in zip(params, args):
                self.scopes[-1][param_name] = arg
                self.var_types[-1][param_name] = param_type

            try:
                for stmt in body:
                    self.visit(stmt)
            except ReturnException as ret:
                result = ret.value
            else:
                result = None

            self.scopes.pop()  # Usuwamy scope po zakończeniu funkcji
            self.var_types.pop()  # Usuwamy typy po zakończeniu funkcji

            return result

        # Zapisanie funkcji jako obiektu wywoływalnego
        self.functions[name] = function_wrapper

        return None

        
    def visitSelectExpr(self, ctx):
        source_ctx = ctx.expr(1)
        source = self.visit(source_ctx)
        
        if not isinstance(source, list):
            raise PySQLTypeError(
                "SELECT source must be an array",
                line=source_ctx.start.line,
                context_text=str(source)
            )

        results = []
        for element in source:
            # ZAMIANA memory -> scopes[-1]
            saved_underscore = self.scopes[-1].get('_', None)
            saved_underscore_type = self.var_types[-1].get('_', None)

            self.scopes[-1]['_'] = element  # ZAMIANA memory -> scopes[-1]
            self.var_types[-1]['_'] = (self.infer_type(element), ctx.start.line)  # ZAMIANA var_types

            try:
                if ctx.WHERE():
                    condition_ctx = ctx.expr(2)
                    condition = self.visit(condition_ctx)

                    if not isinstance(condition, bool):
                        raise PySQLTypeError(
                            "WHERE clause must return boolean",
                            line=condition_ctx.start.line,
                            context_text=str(condition)
                        )
                    
                    if not condition:
                        continue

                projection_ctx = ctx.expr(0)
                result = self.visit(projection_ctx)
                results.append(result)

            finally:
                if saved_underscore is not None:
                    self.scopes[-1]['_'] = saved_underscore  # ZAMIANA memory -> scopes[-1]
                    self.var_types[-1]['_'] = saved_underscore_type  # ZAMIANA var_types
                else:
                    if '_' in self.scopes[-1]:  # ZAMIANA memory -> scopes[-1]
                        del self.scopes[-1]['_']
                    if '_' in self.var_types[-1]:  # ZAMIANA var_types
                        del self.var_types[-1]['_']

        if ctx.ORDER():
            order_direction = ctx.DESC() is not None
            try:
                results.sort(reverse=order_direction)
            except TypeError:
                raise PySQLTypeError(
                    "Cannot sort mixed-type arrays",
                    line=ctx.start.line,
                    context_text=str(results)
                )

        return results


    def visitReturnStat(self, ctx):
        val = self.visit(ctx.expr()) if ctx.expr() else None
        raise ReturnException(val)
        
    def visitAssign(self, ctx):
        if ctx.arrayIndex():
            # Obsługa przypisania do indeksu w tablicy
            arr, index = self.visit(ctx.arrayIndex())
            value = self.visit(ctx.expr())

            # Sprawdzenie typów
            if isinstance(arr, list) and arr:
                elem_type = self.infer_type(arr[0])
                value_type = self.infer_type(value)

                if elem_type == 'float' and value_type == 'int':
                    value = float(value)
                elif not self.type_matches(elem_type, value_type):
                    raise PySQLTypeError(
                        f"Type mismatch: array contains {elem_type}, assigned value is {value_type}",
                        line=ctx.start.line,
                        context_text=str(value)
                    )

            arr[index] = value
            return value
        else:
            var_name = ctx.identifierName().getText()
            value = self.visit(ctx.expr())
            line = ctx.start.line

            if value is None:
                raise Exception(f"Invalid value assigned to '{var_name}' at line {line}")

            value_type = self.infer_type(value)

            # Obsługa `parent::`
            if ctx.parentAccess():
                levels = len(ctx.parentAccess())
                scope_index = -levels - 1

                if abs(scope_index) > len(self.scopes):
                    raise Exception(f"Parent scope access out of bounds: {'parent::' * levels}{var_name}")

                if var_name in self.scopes[scope_index]:
                    self.scopes[scope_index][var_name] = value
                    return value
                else:
                    raise Exception(f"Undefined variable '{var_name}' in parent scopes at line {line}")

            # Normalne przypisanie do aktualnego scope'a
            if var_name in self.scopes[-1]:
                declared_type, decl_line = self.var_types[-1].get(var_name, (None, None))

                if declared_type == 'float' and value_type == 'int':
                    value = float(value)
                    value_type = 'float'

                if declared_type and not self.type_matches(declared_type, value_type):
                    raise Exception(f"Type mismatch on assignment to '{var_name}' at line {line}. Declared as {declared_type} at line {decl_line}, assigned value of type {value_type}")
            else:
                self.var_types[-1][var_name] = (value_type, line)

            self.scopes[-1][var_name] = value
            return value

    
    def infer_type(self, value):
        if isinstance(value, list):
            if not value:
                return 'array<mixed>'
            
            elem_types = {self.infer_type(elem) for elem in value}
            
            if elem_types.issubset({'int', 'float'}):
                if 'float' in elem_types:
                    return 'array<float>'
                return 'array<int>'
            elif len(elem_types) == 1:
                return f'array<{next(iter(elem_types))}>'
            else:
                return 'array<mixed>'
        if isinstance(value, bool): return 'bool'
        if isinstance(value, int): return 'int'
        if isinstance(value, float): return 'float'
        if isinstance(value, str): return 'string'
        
        return 'unknown'

    def type_matches(self, declared, actual):
        
        if declared == actual:
            return True
        if declared == 'float' and actual == 'int':
            return True
        if declared == 'mixed' or actual == 'mixed':
            return True
            
        if declared.startswith('array<') and actual.startswith('array<'):
            declared_elem = declared[6:-1]
            actual_elem = actual[6:-1]
            
            if declared_elem == 'mixed' or actual_elem == 'mixed':
                return True
            if declared_elem == 'float' and actual_elem == 'int':
                return True
            return declared_elem == actual_elem
            
        return False

    def visitArrayLiteral(self, ctx):
        elements = [self.visit(expr) for expr in ctx.expr()] if ctx.expr() else []
        return elements
    
    def visitArrayIndex(self, ctx):
        array_name = ctx.identifierName().getText()
        index_expr = ctx.expr()
        index_val = self.visit(index_expr)

        # Obsługa `parent::`
        if ctx.parentAccess():
            levels = len(ctx.parentAccess())
            scope_index = -levels - 1

            if abs(scope_index) > len(self.scopes):
                raise Exception(f"Parent scope access out of bounds: {'parent::' * levels}{array_name}")

            if array_name in self.scopes[scope_index]:
                arr = self.scopes[scope_index][array_name]
            else:
                suggestion = get_closest_match(array_name, self.scopes[scope_index].keys())
                raise PySQLNameError(
                    f"Undefined array '{array_name}' in parent scopes",
                    line=ctx.start.line,
                    context_text=array_name,
                    suggestion=suggestion
                )
        else:
            if array_name not in self.scopes[-1]:  # ZAMIANA memory -> scopes[-1]
                suggestion = get_closest_match(array_name, self.scopes[-1].keys())  # ZAMIANA memory.keys() -> scopes[-1].keys()
                raise PySQLNameError(
                    f"Undefined array '{array_name}'",
                    line=ctx.start.line,
                    context_text=array_name,
                    suggestion=suggestion
                )

            arr = self.scopes[-1][array_name]  # ZAMIANA memory -> scopes[-1]

        if not isinstance(arr, list):
            raise PySQLTypeError(
                f"Variable '{array_name}' is not an array",
                line=ctx.start.line,
                context_text=array_name
            )

        if not isinstance(index_val, int):
            raise PySQLTypeError(
                "Array index must be an integer",
                line=index_expr.start.line,
                context_text=str(index_val)
            )

        if index_val < 0 or index_val >= len(arr):
            raise PySQLValueError(
                f"Array index out of bounds: {index_val}",
                line=index_expr.start.line,
                context_text=str(index_val)
            )

        return arr, index_val

    
    def visitLogicalExpr(self, ctx):
        left = self.visit(ctx.comparisonExpr(0))
        for i in range(1, len(ctx.comparisonExpr())):
            op = ctx.getChild(2*i-1).getText()
            right = self.visit(ctx.comparisonExpr(i))
            
            if not isinstance(left, bool) or not isinstance(right, bool):
                raise Exception(f"Logical operator '{op}' requires boolean operands at line {ctx.start.line}")
            
            if op == 'and':
                left = left and right
            elif op == 'or':
                left = left or right
        return left


    def visitComparisonExpr(self, ctx):
        left = self.visit(ctx.addExpr(0))
        if ctx.addExpr(1):
            op = ctx.getChild(1).getText()
            right = self.visit(ctx.addExpr(1))
            
            if op in ['==', '!=']:
                if type(left) != type(right):
                    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                        pass
                    else:
                        raise Exception(f"Incompatible types for comparison '{op}' at line {ctx.start.line}")
            else:
                if not (isinstance(left, (int, float)) and isinstance(right, (int, float))):
                    raise Exception(f"Operator '{op}' requires numeric operands at line {ctx.start.line}")
            
            if op == '>': return left > right
            if op == '<': return left < right
            if op == '>=': return left >= right
            if op == '<=': return left <= right
            if op == '==': return left == right
            if op == '!=': return left != right
        return left

    def visitAddExpr(self, ctx):
        result = self.visit(ctx.mulExpr(0))
        for i in range(1, len(ctx.mulExpr())):
            op = ctx.getChild(2*i-1).getText()
            right = self.visit(ctx.mulExpr(i))
            result = self.apply_operator(result, op, right, ctx.start.line)
        return result

    def visitMulExpr(self, ctx):
        result = self.visit(ctx.factor(0))
        for i in range(1, len(ctx.factor())):
            op = ctx.getChild(2*i-1).getText()
            right = self.visit(ctx.factor(i))
            result = self.apply_operator(result, op, right, ctx.start.line)
        return result
        
    def visitVarDecl(self, ctx):
        identifier_ctx = ctx.identifierName()
        var_name = identifier_ctx.getText()
        line = ctx.start.line

        if hasattr(identifier_ctx, 'INVALID_NUMBER') and identifier_ctx.INVALID_NUMBER():
            raise Exception(f"An unexpected error occurred: Invalid variable name '{var_name}' at line {line}")

        # Obsługa `parent::`
        scope_index = -1
        if hasattr(identifier_ctx, "parentAccess") and identifier_ctx.parentAccess():
            levels = len(identifier_ctx.parentAccess())  # Poprawne odwołanie do parentAccess()
            scope_index = -levels - 1

            if abs(scope_index) > len(self.scopes):
                raise Exception(f"Parent scope access out of bounds: {'parent::' * levels}{var_name}")

        if var_name in self.var_types[scope_index]:  # Poprawne sprawdzanie w parent scope
            orig_line = self.var_types[scope_index][var_name][1]
            raise Exception(f"Redeclaration of variable '{var_name}' at line {line}, originally declared at line {orig_line}")

        value = self.visit(ctx.expr()) if ctx.expr() else None
        declared_type = ctx.varType().getText()

        if value is not None:
            inferred_type = self.infer_type(value)

            if declared_type.startswith('array<') and inferred_type.startswith('array<'):
                decl_elem = declared_type[6:-1]
                inf_elem = inferred_type[6:-1]

                if decl_elem == 'float' and inf_elem == 'int':
                    value = [float(x) if isinstance(x, int) else x for x in value]
                    inferred_type = 'array<float>'

            if declared_type == 'float' and inferred_type == 'int':
                value = float(value)
                inferred_type = 'float'

            if not self.type_matches(declared_type, inferred_type):
                raise Exception(f"Type mismatch in declaration of '{var_name}' at line {line}: expected {declared_type}, got {inferred_type}")

        # Poprawione zapisywanie zmiennej do właściwego scope'a
        self.scopes[scope_index][var_name] = value
        self.var_types[scope_index][var_name] = (declared_type, line)

        return value




    def visitFactor(self, ctx: PySQLParser.FactorContext):
        if ctx.getChildCount() == 4 and ctx.getChild(1).getText() == '[' and ctx.getChild(3).getText() == ']':
            array_name = ctx.getChild(0).getText()
            
            index_expr_ctx = ctx.getChild(2)
            index_val = self.visit(index_expr_ctx)
            
            if array_name not in self.scopes[-1]:  # ZAMIANA memory -> scopes[-1]
                suggestion = get_closest_match(array_name, self.scopes[-1].keys())  # ZAMIANA memory.keys() -> scopes[-1].keys()
                raise PySQLNameError(
                    f"Undefined array '{array_name}'",
                    line=ctx.start.line,
                    context_text=array_name,
                    suggestion=suggestion
                )

            arr = self.scopes[-1][array_name]  # ZAMIANA memory -> scopes[-1]
            if not isinstance(arr, list):
                raise PySQLTypeError(
                    f"Variable '{array_name}' is not an array",
                    line=ctx.start.line,
                    context_text=array_name
                )
                
            if not isinstance(index_val, int):
                raise PySQLTypeError(
                    "Array index must be an integer",
                    line=index_expr_ctx.start.line,
                    context_text=str(index_val)
                )
                
            try:
                return arr[index_val]
            except IndexError:
                raise PySQLValueError(
                    f"Array index out of bounds: {index_val}",
                    line=index_expr_ctx.start.line,
                    context_text=str(index_val))
    
        if ctx.getChildCount() == 4 and \
           ctx.getChild(0).getText() == '(' and \
           isinstance(ctx.getChild(1), PySQLParser.VarTypeContext) and \
           ctx.getChild(2).getText() == ')':
            target_type_str = ctx.varType().getText()
            value_to_cast = self.visit(ctx.factor()) 

            if target_type_str == 'int':
                if isinstance(value_to_cast, float): return int(value_to_cast)
                if isinstance(value_to_cast, bool): return 1 if value_to_cast else 0
                if isinstance(value_to_cast, int): return value_to_cast
                raise Exception(f"Cannot cast type {self.infer_type(value_to_cast)} to 'int' at line {ctx.start.line}")
            
            elif target_type_str == 'float':
                if isinstance(value_to_cast, int): return float(value_to_cast)
                if isinstance(value_to_cast, bool): return 1.0 if value_to_cast else 0.0
                if isinstance(value_to_cast, float): return value_to_cast
                raise Exception(f"Cannot cast type {self.infer_type(value_to_cast)} to 'float' at line {ctx.start.line}")

            elif target_type_str == 'bool':
                if isinstance(value_to_cast, int): return value_to_cast != 0
                if isinstance(value_to_cast, float): return value_to_cast != 0.0
                if isinstance(value_to_cast, bool): return value_to_cast
                raise Exception(f"Cannot cast type {self.infer_type(value_to_cast)} to 'bool' at line {ctx.start.line}")
            elif target_type_str == 'string':
                if value_to_cast is None:
                    return "null"
                if isinstance(value_to_cast, bool):
                    return "true" if value_to_cast else "false"
                elif isinstance(value_to_cast, list):
                    return self._array_to_literal_string(value_to_cast)
                else:
                    return str(value_to_cast)
                    
            else:
                raise Exception(f"Unsupported cast to type '{target_type_str}' at line {ctx.start.line}")

        elif ctx.getChildCount() == 2 and ctx.getChild(0).getText() in ('+', '-') and isinstance(ctx.factor(), PySQLParser.FactorContext):
            op = ctx.getChild(0).getText()
            value = self.visit(ctx.factor())
            if isinstance(value, bool):
                raise Exception(f"Unary '{op}' cannot be applied to boolean values at line {ctx.start.line}")
            if isinstance(value, (int, float)):
                return -value if op == '-' else value
            else:
                raise Exception(f"Invalid type for unary '{op}' operator at line {ctx.start.line}. Expected number, got {self.infer_type(value)}.")
        
        elif ctx.INT(): return int(ctx.INT().getText())
        elif ctx.FLOAT(): return float(ctx.FLOAT().getText())
        elif ctx.STRING(): return ctx.STRING().getText()[1:-1]
        elif ctx.BOOL(): return ctx.BOOL().getText().lower() == 'true'

        elif ctx.identifierName() and ctx.getChild(1) and ctx.getChild(1).getText() == '(':
            fname = ctx.identifierName().getText()
            args = []
            if ctx.exprList():
                for e_ctx in ctx.exprList().expr():
                    args.append(self.visit(e_ctx))
            
            if fname not in self.functions:
                suggestion_text = get_closest_match(fname, self.functions.keys())
                raise PySQLNameError(
                    f"Undefined function '{fname}'",
                    line=ctx.start.line,
                    column=ctx.start.column,
                    context_text=fname,
                    suggestion=suggestion_text
                )
            
#            params, ret_type, body_stmts = self.functions[fname]
            params, ret_type, func_impl = self.functions[fname]

            if len(args) != len(params):
                raise Exception(f"Function '{fname}' expects {len(params)} args, got {len(args)} at line {ctx.start.line}")

            processed_args = []
            for i, ((pname, ptype), val) in enumerate(zip(params, args)):
                actual_type = self.infer_type(val)
                arg_line = ctx.exprList().expr(i).start.line if ctx.exprList() else ctx.start.line

                if ptype == 'float' and actual_type == 'int':
                    val = float(val)
                    actual_type = 'float'

                if not self.type_matches(ptype, actual_type):
                    raise Exception(f"Incorrect type for parameter '{pname}' in call to '{fname}' at line {arg_line}. Expected {ptype}, got {actual_type}")
                processed_args.append(val)
            
            # Handle built-in functions (direct call)
            if callable(func_impl):
                try:
                    result = func_impl(*processed_args)
                    # Validate return type
                    actual_ret_type = self.infer_type(result)
                    if ret_type == 'float' and actual_ret_type == 'int':
                        result = float(result)
                        actual_ret_type = 'float'
                    if not self.type_matches(ret_type, actual_ret_type):
                        raise PySQLTypeError(
                            f"Function '{fname}' returned incorrect type",
                            line=ctx.start.line,
                            context_text=str(result),
                            suggestion=f"Expected {ret_type}, got {actual_ret_type}"
                        )
                    return result
                except PySQLException as e:
                    if e.line is None:
                        e.line = ctx.start.line
                    raise e
                except Exception as e:
                    raise PySQLRuntimeError(
                        f"Error in built-in function '{fname}': {str(e)}",
                        line=ctx.start.line,
                        context_text=fname
                    )            
            saved_memory = self.scopes[-1].copy()  # ZAMIANA memory -> scopes[-1]
            saved_types = self.var_types[-1].copy()  # ZAMIANA var_types -> var_types[-1]
            current_call_line = ctx.start.line

            for i, ((pname, ptype), val) in enumerate(zip(params, processed_args)):
                self.scopes[-1][pname] = val  # ZAMIANA memory -> scopes[-1]
                self.var_types[-1][pname] = (ptype, current_call_line)  # ZAMIANA var_types -> var_types[-1]

            try:
                for stmt_ctx in func_impl:
                    self.visit(stmt_ctx)
            except ReturnException as r:
                result = r.value
                if ret_type != 'void':
                    actual_ret_type = self.infer_type(result)
                    if ret_type == 'float' and actual_ret_type == 'int':
                        result = float(result)
                        actual_ret_type = 'float'
                    if not self.type_matches(ret_type, actual_ret_type):
                        raise Exception(f"Function '{fname}' should return {ret_type}, got {actual_ret_type}. Called at line {current_call_line}")

                self.scopes[-1] = saved_memory  # ZAMIANA memory -> scopes[-1]
                self.var_types[-1] = saved_types  # ZAMIANA var_types -> var_types[-1]
                return result

            self.scopes[-1] = saved_memory  # ZAMIANA memory -> scopes[-1]
            self.var_types[-1] = saved_types  # ZAMIANA var_types -> var_types[-1]

            if ret_type != 'void':
                raise Exception(f"Function '{fname}' defined with return type '{ret_type}' did not return a value. Called at line {current_call_line}")
            return None


        # Obsługa zmiennych
        elif ctx.identifierName():
            var_name = ctx.identifierName().getText()
            if var_name not in self.scopes[-1]:  # Zamiana memory -> scopes[-1]
                suggestion_text = get_closest_match(var_name, self.scopes[-1].keys())
                raise PySQLNameError(
                    f"Undefined variable '{var_name}'",
                    line=ctx.start.line,
                    column=ctx.start.column,
                    context_text=var_name,
                    suggestion=suggestion_text
                )
            return self.scopes[-1][var_name]  # Zamiana memory -> scopes[-1]

        elif ctx.getChildCount() == 2 and ctx.getChild(0).getText() == 'not':
            val_to_negate = self.visit(ctx.factor())
            if not isinstance(val_to_negate, bool):
                raise Exception(f"'not' operator requires a boolean operand, got {self.infer_type(val_to_negate)} at line {ctx.start.line}")
            return not val_to_negate

        elif ctx.expr() and ctx.getChildCount() == 3 and \
             ctx.getChild(0).getText() == '(' and \
             isinstance(ctx.expr(), PySQLParser.ExprContext) and \
             ctx.getChild(2).getText() == ')':
            return self.visit(ctx.expr())
        
        elif ctx.arrayLiteral():
            return self.visit(ctx.arrayLiteral())
            
        elif ctx.arrayIndex():
            arr, index = self.visit(ctx.arrayIndex())
            return arr[index]

        elif ctx.selectExpr():
            return self.visit(ctx.selectExpr())

        else:
            raise Exception(f"Invalid or unhandled factor structure near '{ctx.getText()}' at line {ctx.start.line}")

    def _array_to_literal_string(self, arr):
        elements = []
        for item in arr:
            if isinstance(item, bool):
                s = "true" if item else "false"
            elif isinstance(item, str):
                escaped = item.replace('\\', '\\\\').replace('"', '\\"')
                s = '"' + escaped + '"'
            elif isinstance(item, list):
                s = self._array_to_literal_string(item)
            else:
                s = str(item)
            elements.append(s)
        return '[' + ', '.join(elements) + ']'
    
    # String functions
    def builtin_toUpper(self, s):
        if not isinstance(s, str):
            raise PySQLTypeError("toUpper expects a string argument", context_text=str(s))
        return s.upper()

    def builtin_toLower(self, s):
        if not isinstance(s, str):
            raise PySQLTypeError("toLower expects a string argument", context_text=str(s))
        return s.lower()

    def builtin_startsWith(self, s, prefix):
        if not isinstance(s, str) or not isinstance(prefix, str):
            raise PySQLTypeError("startsWith expects two string arguments")
        return s.startswith(prefix)

    def builtin_endsWith(self, s, suffix):
        if not isinstance(s, str) or not isinstance(suffix, str):
            raise PySQLTypeError("endsWith expects two string arguments")
        return s.endswith(suffix)

    def builtin_contains(self, s, substring):
        if not isinstance(s, str) or not isinstance(substring, str):
            raise PySQLTypeError("contains expects two string arguments")
        return substring in s

    # Numerical aggregation functions
    def builtin_sum(self, arr):
        if not isinstance(arr, list):
            raise PySQLTypeError("sum expects an array argument", context_text=str(arr))
        if not all(isinstance(x, (int, float)) for x in arr):
            raise PySQLTypeError("sum expects a numerical array")
        return sum(arr)

    def builtin_avg(self, arr):
        if not isinstance(arr, list):
            raise PySQLTypeError("avg expects an array argument", context_text=str(arr))
        if not arr:
            raise PySQLValueError("avg cannot be calculated for empty array")
        if not all(isinstance(x, (int, float)) for x in arr):
            raise PySQLTypeError("avg expects a numerical array")
        return sum(arr) / len(arr)

    def builtin_min(self, arr):
        if not isinstance(arr, list):
            raise PySQLTypeError("min expects an array argument", context_text=str(arr))
        if not arr:
            raise PySQLValueError("min cannot be calculated for empty array")
        if not all(isinstance(x, (int, float)) for x in arr):
            raise PySQLTypeError("min expects a numerical array")
        return min(arr)

    def builtin_max(self, arr):
        if not isinstance(arr, list):
            raise PySQLTypeError("max expects an array argument", context_text=str(arr))
        if not arr:
            raise PySQLValueError("max cannot be calculated for empty array")
        if not all(isinstance(x, (int, float)) for x in arr):
            raise PySQLTypeError("max expects a numerical array")
        return max(arr)

    def builtin_count(self, arr):
        if not isinstance(arr, list):
            raise PySQLTypeError("count expects an array argument", context_text=str(arr))
        return len(arr)

    def builtin_median(self, arr):
        if not isinstance(arr, list):
            raise PySQLTypeError("median expects an array argument", context_text=str(arr))
        if not arr:
            raise PySQLValueError("median cannot be calculated for empty array")
        if not all(isinstance(x, (int, float)) for x in arr):
            raise PySQLTypeError("median expects a numerical array")
            
        sorted_arr = sorted(arr)
        n = len(sorted_arr)
        mid = n // 2
        
        if n % 2 == 1:
            return sorted_arr[mid]
        else:
            return (sorted_arr[mid - 1] + sorted_arr[mid]) / 2.0

    def builtin_length(self, arr):
        if isinstance(arr, str):   # Handle strings
            return len(arr)
        elif isinstance(arr, list):  # Handle arrays
            return len(arr)
        else:
            raise TypeError(f"Unsupported type for len(): {type(arr).__name__}")
        
    def builtin_type(self, value):
        if value is None:
            return "null"
        
        if isinstance(value, bool):
            return "bool"
        if isinstance(value, int):
            return "int"
        if isinstance(value, float):
            return "float"
        if isinstance(value, str):
            return "string"
        if isinstance(value, list):
            if not value:
                return "array<empty>"
            
            elem_types = {self.builtin_type(elem) for elem in value}
            
            if len(elem_types) == 1:
                return f"array<{next(iter(elem_types))}>"
            else:
                return "array<mixed>"
        
        return "unknown"

    def apply_operator(self, left, op, right, line):
        try:
            if op == '+':
                if isinstance(left, bool) or isinstance(right, bool):
                    raise Exception(f"Boolean values cannot be used in arithmetic operations at line {line}")
                if isinstance(left, str) and isinstance(right, str):
                    return left + right
                elif isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return left + right
                else:
                    raise TypeError()

            elif op in ('-', '*', '/'):
                self.check_numeric(left, right, line)
                if op == '-': return left - right
                if op == '*': return left * right
                if op == '/':
                    if right == 0:
                        raise ZeroDivisionError()
                    if isinstance(left, int) and isinstance(right, int):
                        return left // right
                    else:
                        return left / right

        except TypeError:
            raise Exception(f"Incompatible types for '{op}' at line {line}")
        except ZeroDivisionError:
            raise Exception(f"Division by zero at line {line}")

    def check_numeric(self, left, right, line):
        if not (isinstance(left, (int, float)) and isinstance(right, (int, float))):
            raise Exception(f"Invalid types for arithmetic operation at line {line}")
        if isinstance(left, bool) or isinstance(right, bool):
            raise Exception(f"Boolean values cannot be used in arithmetic operations at line {line}")

    def visitPrintStat(self, ctx):
        value = self.visit(ctx.expr())
        print(value)
        return value
    
    def visitProg(self, ctx):
        for child in ctx.stat():
            self.visit(child)


    def visitIfStat(self, ctx):
        condition = self.visit(ctx.expr())
        if not isinstance(condition, bool):
            line = ctx.expr().start.line
            raise Exception(f"Condition must be a boolean, got {type(condition)} at line {line}")
        # Izolacja zmiennych dla bloku 'if'
        self.scopes.append({})
        self.var_types.append({})

        result = self.visit(ctx.stat(0) if condition else ctx.stat(1) if ctx.stat(1) else None)

        # Powrót do poprzedniego zakresu po wykonaniu bloku
        self.scopes.pop()
        self.var_types.pop()

        return result

    def visitBreakStat(self, ctx):
        raise BreakException()

    def visitContinueStat(self, ctx):
        raise ContinueException()


    def visitWhileLoop(self, ctx):
        """
        Ta metoda obsługuje pętlę 'while'.
        Jest to ta sama logika, która była w Twoim 'if' w visitLoopStat.
        """
        while True:
            condition = self.visit(ctx.expr())
            if not isinstance(condition, bool):
                raise Exception(f"'while' condition must be boolean at line {ctx.start.line}")
            if not condition:
                break
            # Dodanie nowego scope'a dla każdej iteracji pętli
            self.scopes.append({})
            self.var_types.append({})

            try:
                self.visit(ctx.block())
            except BreakException:
                self.scopes.pop()  # Usunięcie zakresu przed przerwaniem pętli
                self.var_types.pop()
                break
            except ContinueException:
                self.scopes.pop()  # Usunięcie zakresu przed kontynuowaniem pętli
                self.var_types.pop()
                continue
            # Usunięcie zakresu po zakończeniu iteracji
            self.scopes.pop()
            self.var_types.pop()

    def visitForLoop(self, ctx):
        """
        NOWA, elastyczna implementacja pętli 'for' pasująca do nowej gramatyki.
        """

        # Dodanie nowego scope'a dla pętli
        self.scopes.append({})
        self.var_types.append({})

        if ctx.forInitializer():
            self.visit(ctx.forInitializer())

        while True:
            condition = True
            if ctx.expr():
                condition_val = self.visit(ctx.expr())
                if not isinstance(condition_val, bool):
                    raise Exception(f"'for' condition must be a boolean at line {ctx.start.line}")
                condition = condition_val
            
            if not condition:
                break

            try:
                self.visit(ctx.block())
            except BreakException:
                break
            except ContinueException:
                if ctx.forUpdate():
                    self.visit(ctx.forUpdate())
                continue

            if ctx.forUpdate():
                self.visit(ctx.forUpdate())

        # Usunięcie zakresu po zakończeniu pętli
        self.scopes.pop()
        self.var_types.pop()

    
    def visitBlock(self, ctx):
        # Dodanie nowego scope'a dla bloku kodu
        self.scopes.append({})
        self.var_types.append({})
        for stmt in ctx.stat():
            self.visit(stmt)
        # Usunięcie zakresu po zakończeniu bloku
        self.scopes.pop()
        self.var_types.pop()

    
class BreakException(Exception): pass
class ContinueException(Exception): pass



class PySQLErrorListener(ErrorListener):
    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e: RecognitionException):
        error_message = msg
        context_text = None
        suggestion = None   # Na razie nie implementujemy sugestii dla błędów składniowych

        if offendingSymbol is not None:
            context_text = offendingSymbol.text

        # --- Obsługa błędów Leksera ---
        if isinstance(e, LexerNoViableAltException):
            char_in_error = self._get_char_error_display(e.input, e.startIndex)
            error_message = f"Unrecognized character or sequence starting with '{char_in_error}'"
            
            # Sprawdzenie, czy błąd pochodzi z naszej akcji leksykalnej (np. INVALID_NUMBER)
            if e.__cause__ is not None:
                original_exception_message = str(e.__cause__)
                if "Invalid number format" in original_exception_message:
                    error_message = original_exception_message
                    # context_text może być już częścią original_exception_message
                    # np. "Invalid number format: 123bad"
                    # Jeśli offendingSymbol.text jest bardziej precyzyjny, można go użyć.
                    if offendingSymbol is not None: # Dla INVALID_NUMBER, offendingSymbol to cały błędny token
                         context_text = offendingSymbol.text


        # --- Obsługa błędów Parsera ---
        elif isinstance(e, InputMismatchException):
            found_token_display = self._get_token_display_name(recognizer, offendingSymbol)
            expected_desc = self._get_expected_tokens_description(recognizer, recognizer.getExpectedTokens())
            if offendingSymbol and offendingSymbol.type == Token.EOF:
                error_message = f"Unexpected end of file; expecting {expected_desc}"
                context_text = "end of file"
            else:
                error_message = f"Unexpected {found_token_display}; expecting {expected_desc}"
        
        elif isinstance(e, NoViableAltException):
            # Ten błąd oznacza, że parser nie mógł dopasować żadnej alternatywy w regule.
            # offendingSymbol to token, przy którym parser utknął.
            token_display = self._get_token_display_name(recognizer, offendingSymbol)
            error_message = f"Invalid or incomplete statement near {token_display}. Cannot determine how to proceed."
            # Można spróbować uzyskać oczekiwane tokeny, ale dla NoViableAltException może to być mniej precyzyjne.
            # expected_desc = self._get_expected_tokens_description(recognizer, recognizer.getExpectedTokens())
            # if expected_desc:
            #     error_message += f" Were you trying to write {expected_desc}?"

        elif isinstance(e, FailedPredicateException):
            token_display = self._get_token_display_name(recognizer, offendingSymbol)
            predicate_text = e.predicate if e.predicate else "a specific condition"
            # rule_name = recognizer.ruleNames[e.ruleIndex] # Nazwa reguły, w której predykat zawiódł
            error_message = f"A grammar condition (predicate) was not met near {token_display} (failed: {predicate_text})"
        
        # --- Inne lub nieokreślone błędy rozpoznawania ---
        # Jeśli 'e' nie jest None, ale nie pasuje do powyższych, użyj domyślnego 'msg'.
        # 'msg' często jest już sformatowane przez ANTLR (np. "missing X", "extraneous Y").
        # Można tutaj dodać logikę do "oczyszczania" lub upraszczania tych domyślnych wiadomości.
        elif msg: # Jeśli 'e' jest innego typu lub None, ale 'msg' istnieje
            error_message = msg # Użyj domyślnego komunikatu

        # Domyślny context_text, jeśli nie został ustawiony przez konkretny handler błędu
        if context_text is None and offendingSymbol is not None:
            context_text = offendingSymbol.text
        elif context_text is None and e is not None and hasattr(e, 'offendingToken') and e.offendingToken is not None:
            context_text = e.offendingToken.text


        raise PySQLSyntaxError(
            message=error_message,
            line=line,
            column=column, # Przekazujemy kolumnę, ale __str__ w PySQLSyntaxError ją pominie
            context_text=context_text,
            suggestion=suggestion
        )

    def _get_char_error_display(self, input_stream: InputStream, start_index: int) -> str:
        """Pomocnik do wyświetlania znaku, który spowodował błąd leksera."""
        if input_stream is not None and 0 <= start_index < input_stream.size:
            char = input_stream.getText(start_index, start_index)
            if char == '\n': return "\\n"
            if char == '\r': return "\\r"
            if char == '\t': return "\\t"
            if char == str(Token.EOF): return "<EOF>" # Teoretycznie nie powinno tu być EOF
            return char
        return "<unknown char>"

    def _get_token_display_name(self, recognizer, token: Token) -> str:
        """Zwraca czytelną nazwę dla tokenu."""
        if token is None:
            return "<no token>"
        if token.type == Token.EOF:
            return "<end of file>"
        # recognizer.vocabulary.getDisplayName(token.type) jest preferowane
        if hasattr(recognizer, 'vocabulary'):
            name = recognizer.vocabulary.getDisplayName(token.type)
            # Jeśli nazwa to literał (np. "'+'"), zwróć go. Jeśli symboliczna (np. "ID"), zwróć tekst tokenu.
            if name == token.text or (name.startswith("'") and name.endswith("'")):
                return name 
            return f"{name} ('{token.text}')" # Np. "ID ('myVar')"
        return f"token '{token.text}' (type {token.type})"


    def _get_expected_tokens_description(self, recognizer, interval_set: IntervalSet) -> str:
        """Tworzy czytelny opis oczekiwanych tokenów."""
        if interval_set is None or not hasattr(recognizer, 'vocabulary'):
            return "a specific token or sequence"

        expected_names = []
        for i in range(interval_set.min_element, interval_set.max_element + 1):
            if not interval_set.contains(i):
                continue

            display_name = recognizer.vocabulary.getDisplayName(i)
            if i == Token.EOF:
                if len(interval_set) < 5 :
                    expected_names.append("end of file")
            elif i > 0:
                if display_name.startswith("'") and display_name.endswith("'"):
                    expected_names.append(display_name)  # np. "'if'", "'+'"
                else:
                    article = "an" if display_name and display_name[0].lower() in "aeiouh" else "a"
                    expected_names.append(f"{article} {display_name.lower()}")
        
        # Usuń duplikaty i ewentualnie posortuj
        unique_token_names = sorted(list(set(expected_names)))
        
        if not unique_token_names:
            return "a valid statement component"
        if len(unique_token_names) == 1:
            return unique_token_names[0]
        # Ogranicz liczbę wyświetlanych oczekiwanych tokenów, aby nie przytłoczyć użytkownika
        if len(unique_token_names) > 4:
             # Weź pierwsze kilka i dodaj "..."
            return "one of: " + ", ".join(unique_token_names[:3]) + ", or others"

        return "one of: " + ", ".join(unique_token_names[:-1]) + " or " + unique_token_names[-1]

# Uruchamianie interpretera

def run_interpreter(input_code, base_dir=""):
    lexer = PySQLLexer(InputStream(input_code))
    lexer.removeErrorListeners()
    lexer.addErrorListener(PySQLErrorListener())

    stream = CommonTokenStream(lexer)
    parser = PySQLParser(stream)
    parser.removeErrorListeners()
    parser.addErrorListener(PySQLErrorListener())

    try:
        tree = parser.prog()
        interpreter = PySQLInterpreter(base_dir)
        interpreter.visit(tree)
    except PySQLException as e: # Łap bazowy wyjątek PySQL
        print(e) # __str__ z niestandardowego wyjątku zostanie użyty
    except Exception as e: # Dla innych, nieprzewidzianych błędów
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python your_script.py <filename>")
        sys.exit(1)

    filename = sys.argv[1]
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            input_code = f.read()
        base_dir = os.path.dirname(os.path.abspath(filename))
        run_interpreter(input_code, base_dir)
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
    except Exception as e:
        print(f"An error occurred: {e}")