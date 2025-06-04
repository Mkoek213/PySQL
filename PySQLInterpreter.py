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
        self.memory = {}
        self.var_types = {}
        self.functions = {}
        self.base_dir = base_dir 

        if shared_import_context is None:
            self.shared_import_context = {
                'globally_parsed_modules': {}, # file_path -> {'memory':..., 'functions':..., 'var_types':...}
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
            'memory': module_interpreter.memory.copy(),
            'functions': module_interpreter.functions.copy(),
            'var_types': module_interpreter.var_types.copy()
        }

        self.shared_import_context['globally_parsed_modules'][file_path_to_import] = module_state
        self.shared_import_context['currently_parsing'].remove(file_path_to_import)

        return module_state
    
    def visitFullImport(self, ctx: PySQLParser.FullImportContext): # Parameter type from ANTLR
        path_raw = ctx.STRING().getText()[1:-1] # Get "file.txt"

        module_state = self._get_or_parse_module(path_raw)

        for name, value in module_state['memory'].items():
            if name in self.functions: # Check for clash with existing function in current scope
                raise Exception(f"Name clash during full import from '{path_raw}': Cannot import variable '{name}', a function with this name already exists in the current scope.")
            self.memory[name] = value
            if name in module_state['var_types']: # Also copy type information
                self.var_types[name] = module_state['var_types'][name]

        for name, func_def in module_state['functions'].items():
            if name in self.memory:  # Check for clash with existing variable in current scope
                raise Exception(f"Name clash during full import from '{path_raw}': Cannot import function '{name}', a variable with this name already exists in the current scope.")
            self.functions[name] = func_def

        return None 
    
    def visitSelectiveImport(self, ctx: PySQLParser.SelectiveImportContext): # Parameter type from ANTLR
        path_raw = ctx.STRING().getText()[1:-1] # Get "file.txt"

        items_to_import = [id_node.getText() for id_node in ctx.idList().ID()]

        module_state = self._get_or_parse_module(path_raw)

        for item_name in items_to_import:
            imported_successfully = False

            if item_name in module_state['memory']:
                if item_name in self.functions: # Clash with existing function in current scope
                    raise Exception(f"Name clash while importing '{item_name}' from '{path_raw}': A function with this name already exists in the current scope.")
                self.memory[item_name] = module_state['memory'][item_name]
                if item_name in module_state['var_types']:
                    self.var_types[item_name] = module_state['var_types'][item_name]
                imported_successfully = True

            if item_name in module_state['functions']:
                if not imported_successfully: # Not yet imported as a variable
                    if item_name in self.memory: # Clash with existing variable in current scope
                        raise Exception(f"Name clash while importing function '{item_name}' from '{path_raw}': A variable with this name already exists in the current scope.")
                    self.functions[item_name] = module_state['functions'][item_name]
                    imported_successfully = True

            if not imported_successfully:
                raise Exception(f"Item '{item_name}' not found as variable or function in module '{path_raw}' (imported at line {ctx.start.line})")

        return None
    
    def visitFuncDef(self, ctx):
        name = ctx.ID().getText()
        if name in self.functions:
            raise Exception(f"Function '{name}' already defined at line {ctx.start.line}")
        # parameters: list of (name, type)
        params = []
        if ctx.paramList():
            ids = ctx.paramList().ID()
            types = ctx.paramList().varType()
            for pname_ctx, ptype_ctx in zip(ids, types):
                params.append((pname_ctx.getText(), ptype_ctx.getText()))
        ret_type = ctx.returnType().getText()
        body = ctx.stat()
        self.functions[name] = (params, ret_type, body)
        return None

    def visitReturnStat(self, ctx):
        val = self.visit(ctx.expr()) if ctx.expr() else None
        raise ReturnException(val)
    def visitAssign(self, ctx):
        var_name = ctx.ID().getText()
        value = self.visit(ctx.expr())
        line = ctx.start.line

        if value is None: # Should not happen if expr always yields a value
            raise Exception(f"Invalid value assigned to '{var_name}' at line {line}")

        value_type = self.infer_type(value)

        if var_name in self.var_types:
            declared_type, decl_line = self.var_types[var_name]

            # Implicit promotion from int to float
            if declared_type == 'float' and value_type == 'int':
                value = float(value)
                value_type = 'float' # Update value_type after promotion

            if not self.type_matches(declared_type, value_type):
                raise Exception(f"Type mismatch on assignment to '{var_name}' at line {line}. Declared as {declared_type} at line {decl_line}, assigned value of type {value_type}")
        else:
            # Variable not declared, infer its type from this first assignment
            self.var_types[var_name] = (value_type, line)

        self.memory[var_name] = value
        return value
    
    def infer_type(self, value):
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
        return False


    
    def visitLogicalExpr(self, ctx):
        left = self.visit(ctx.comparisonExpr(0))
        for i in range(1, len(ctx.comparisonExpr())):
            op = ctx.getChild(2*i-1).getText()
            right = self.visit(ctx.comparisonExpr(i))
            
            # Dodaj walidację: tylko bool and bool
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
                # Tylko porównywalne typy (int/float) lub ten sam typ
                if type(left) != type(right):
                    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                        pass  # OK: float vs int
                    else:
                        raise Exception(f"Incompatible types for comparison '{op}' at line {ctx.start.line}")
            else:
                # Other operators require numeric types
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
        declared_type = ctx.varType().getText()
        var_name = ctx.ID().getText()
        line = ctx.start.line

        if var_name in self.var_types:
            orig_line = self.var_types[var_name][1]
            raise Exception(f"Redeclaration of variable '{var_name}' at line {line}, originally declared at line {orig_line}")

        value = self.visit(ctx.expr()) if ctx.expr() else None
        if value is not None:
            inferred_type = self.infer_type(value)

            # Implicit promotion from int to float
            if declared_type == 'float' and inferred_type == 'int':
                value = float(value)
                inferred_type = 'float' # Update inferred_type after promotion

            if not self.type_matches(declared_type, inferred_type): # type_matches already allows int for float
                raise Exception(f"Type mismatch in declaration of '{var_name}' at line {line}: expected {declared_type}, got {inferred_type}")

        self.memory[var_name] = value
        self.var_types[var_name] = (declared_type, line)
        return value


    def visitFactor(self, ctx: PySQLParser.FactorContext):
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

        elif ctx.ID() and ctx.getChild(1) and ctx.getChild(1).getText() == '(':
            fname = ctx.ID().getText()
            args = []
            if ctx.exprList():
                for e_ctx in ctx.exprList().expr():
                    args.append(self.visit(e_ctx))
            
            if fname not in self.functions:
                # TUTAJ: Dodaj logikę sugestii
                suggestion_text = get_closest_match(fname, self.functions.keys())
                raise PySQLNameError(
                    f"Undefined function '{fname}'",
                    line=ctx.start.line,
                    column=ctx.start.column,
                    context_text=fname,
                    suggestion=suggestion_text
                )
            
            params, ret_type, body_stmts = self.functions[fname]

            if len(args) != len(params):
                raise Exception(f"Function '{fname}' expects {len(params)} args, got {len(args)} at line {ctx.start.line}")

            saved_memory = self.memory.copy()
            saved_types = self.var_types.copy()
            current_call_line = ctx.start.line

            for i, ((pname, ptype), val) in enumerate(zip(params, args)):
                actual_type = self.infer_type(val)
                arg_line = ctx.exprList().expr(i).start.line if ctx.exprList() and ctx.exprList().expr(i) else current_call_line

                if ptype == 'float' and actual_type == 'int':
                    val = float(val)
                    actual_type = 'float'

                if not self.type_matches(ptype, actual_type):
                     raise Exception(f"Incorrect type for parameter '{pname}' (index {i}) in call to '{fname}' at line {arg_line}. Expected {ptype}, got {actual_type}")
                self.memory[pname] = val
                self.var_types[pname] = (ptype, arg_line)
            
            try:
                for stmt_ctx in body_stmts:
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
                self.memory = saved_memory
                self.var_types = saved_types
                return result
            
            self.memory = saved_memory
            self.var_types = saved_types
            if ret_type != 'void':
                 raise Exception(f"Function '{fname}' defined with return type '{ret_type}' did not return a value. Called at line {current_call_line}")
            return None

        elif ctx.ID(): # Gdy odwołujesz się do zmiennej
            var_name = ctx.ID().getText()
            if var_name not in self.memory:
                # TUTAJ: Dodaj logikę sugestii
                suggestion_text = get_closest_match(var_name, self.memory.keys())
                raise PySQLNameError(
                    f"Undefined variable '{var_name}'",
                    line=ctx.start.line,
                    column=ctx.start.column,
                    context_text=var_name,
                    suggestion=suggestion_text
                )
            return self.memory[var_name]

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
            raise NotImplementedError(f"Array literal handling not fully implemented in visitFactor at line {ctx.start.line}")

        elif ctx.selectExpr():
            return self.visit(ctx.selectExpr())

        else:
            raise Exception(f"Invalid or unhandled factor structure near '{ctx.getText()}' at line {ctx.start.line}")

    def apply_operator(self, left, op, right, line):
        try:
            if op == '+':
                if isinstance(left, bool) or isinstance(right, bool):
                    raise Exception(f"Boolean values cannot be used in arithmetic operations at line {line}")
                # Dopuszczamy tylko: liczba + liczba LUB string + string
                if isinstance(left, str) and isinstance(right, str):
                    return left + right
                elif isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return left + right
                else:
                    raise TypeError()

            elif op in ('-', '*', '/'):
                # Wymagamy dwóch liczb i blokujemy boolean
                self.check_numeric(left, right, line)
                if op == '-': return left - right
                if op == '*': return left * right
                if op == '/':
                    if right == 0:
                        raise ZeroDivisionError()
                    if isinstance(left, int) and isinstance(right, int):
                        return left // right  # <== ZMIANA TUTAJ
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
        # Check if the condition is a boolean
        if not isinstance(condition, bool):
            line = ctx.expr().start.line
            raise Exception(f"Condition must be a boolean, got {type(condition)} at line {line}")
        if condition:
            return self.visit(ctx.stat(0))
        elif ctx.stat(1):
            return self.visit(ctx.stat(1))
        return None

    def visitBreakStat(self, ctx):
        raise BreakException()

    def visitContinueStat(self, ctx):
        raise ContinueException()


    def visitLoopStat(self, ctx):
        if ctx.getChild(0).getText() == 'while':
            while True:
                condition = self.visit(ctx.expr())
                if not isinstance(condition, bool):
                    raise Exception(f"'while' condition must be boolean at line {ctx.start.line}")
                if not condition:
                    break
                try:
                    self.visit(ctx.block())
                except BreakException:
                    break
                except ContinueException:
                    continue

        elif ctx.getChild(0).getText() == 'for':
            init = ctx.assign(0)
            cond = ctx.expr()
            incr = ctx.assign(1)
            self.visit(init)
            while self.visit(cond):
                try:
                    self.visit(ctx.block())
                except BreakException:
                    break
                except ContinueException:
                    pass  
                self.visit(incr)
    
    def visitBlock(self, ctx):
        for stmt in ctx.stat():
            self.visit(stmt)

    
class BreakException(Exception): pass
class ContinueException(Exception): pass



class PySQLErrorListener(ErrorListener):
    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e: RecognitionException):
        error_message = msg  # Domyślny komunikat ANTLR
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
        # Iteracja po elementach IntervalSet (które są typami tokenów)
        for i in range(interval_set.min_element, interval_set.max_element + 1): # Uproszczona iteracja, IntervalSet może mieć dziury
            if not interval_set.contains(i):
                continue

            display_name = recognizer.vocabulary.getDisplayName(i)
            if i == Token.EOF:
                # Dodaj EOF tylko jeśli jest to jedno z niewielu oczekiwań
                if len(interval_set) < 5 : # Arbitralny próg, żeby nie zaśmiecać
                    expected_names.append("end of file")
            elif i > 0: # Prawidłowe typy tokenów
                if display_name.startswith("'") and display_name.endswith("'"):
                    expected_names.append(display_name)  # np. "'if'", "'+'"
                else:
                    # Dla nazw symbolicznych (ID, INT), można je sformatować
                    # Np. "an identifier", "an integer"
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


    

