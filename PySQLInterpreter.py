from antlr4 import *
from antlr4.error.ErrorListener import ErrorListener
from PySQLLexer import PySQLLexer
from PySQLParser import PySQLParser
from PySQLVisitor import PySQLVisitor
import os

# Exception to unwind stack on return
class ReturnException(Exception):
    def __init__(self, value):
        self.value = value

class PySQLInterpreter(PySQLVisitor):
    def __init__(self, base_dir="", shared_import_context=None):
        self.memory = {}
        self.var_types = {}
        self.functions = {}
        self.base_dir = base_dir # Base directory for resolving relative import paths

        if shared_import_context is None:
            # This dictionary will store the state of already parsed modules
            # and a set to track files currently being parsed to detect circular imports.
            self.shared_import_context = {
                'globally_parsed_modules': {}, # file_path -> {'memory':..., 'functions':..., 'var_types':...}
                'currently_parsing': set()     # set of absolute file_paths
            }
        else:
            self.shared_import_context = shared_import_context

           
    def _get_or_parse_module(self, relative_path):
        # Determine the absolute path of the file to import
        # relative_path is from the import statement, e.g., "utils.txt"
        # self.base_dir is the directory of the file *currently being interpreted*
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

        # It's good practice to attach error listeners to these new instances too
        error_listener = PySQLErrorListener() # Assuming PySQLErrorListener is defined
        lexer.removeErrorListeners()
        lexer.addErrorListener(error_listener)
        parser.removeErrorListeners()
        parser.addErrorListener(error_listener)

        tree = parser.prog()

        # Create a new interpreter for the imported file's scope.
        # It gets the base directory of the imported file and shares the import context.
        module_interpreter = PySQLInterpreter(
            base_dir=os.path.dirname(file_path_to_import),
            shared_import_context=self.shared_import_context 
        )

        try:
            module_interpreter.visit(tree) # This populates module_interpreter's state
        except Exception as e:
            # Clean up before re-raising to allow trying to parse this file again if imported elsewhere non-circularly
            self.shared_import_context['currently_parsing'].remove(file_path_to_import)
            raise Exception(f"Error while parsing imported file '{file_path_to_import}': {str(e)}")


        # Store the clean state (memory, functions, types) of the parsed module
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

        # Merge all variables from the imported module into the current scope
        for name, value in module_state['memory'].items():
            if name in self.functions: # Check for clash with existing function in current scope
                raise Exception(f"Name clash during full import from '{path_raw}': Cannot import variable '{name}', a function with this name already exists in the current scope.")
            self.memory[name] = value
            if name in module_state['var_types']: # Also copy type information
                self.var_types[name] = module_state['var_types'][name]

        # Merge all functions from the imported module into the current scope
        for name, func_def in module_state['functions'].items():
            if name in self.memory:  # Check for clash with existing variable in current scope
                raise Exception(f"Name clash during full import from '{path_raw}': Cannot import function '{name}', a variable with this name already exists in the current scope.")
            self.functions[name] = func_def

        return None # Import statements don't produce a value
    
    def visitSelectiveImport(self, ctx: PySQLParser.SelectiveImportContext): # Parameter type from ANTLR
        path_raw = ctx.STRING().getText()[1:-1] # Get "file.txt"

        # Get the list of identifiers to import
        items_to_import = [id_node.getText() for id_node in ctx.idList().ID()]

        module_state = self._get_or_parse_module(path_raw)

        for item_name in items_to_import:
            imported_successfully = False

            # Try to import as a variable
            if item_name in module_state['memory']:
                if item_name in self.functions: # Clash with existing function in current scope
                    raise Exception(f"Name clash while importing '{item_name}' from '{path_raw}': A function with this name already exists in the current scope.")
                self.memory[item_name] = module_state['memory'][item_name]
                if item_name in module_state['var_types']:
                    self.var_types[item_name] = module_state['var_types'][item_name]
                imported_successfully = True

            # Try to import as a function (only if not already imported as a variable with the same name)
            if item_name in module_state['functions']:
                if not imported_successfully: # Not yet imported as a variable
                    if item_name in self.memory: # Clash with existing variable in current scope
                        raise Exception(f"Name clash while importing function '{item_name}' from '{path_raw}': A variable with this name already exists in the current scope.")
                    self.functions[item_name] = module_state['functions'][item_name]
                    imported_successfully = True
                # If imported_successfully is True here, it means item_name was already imported as a variable.
                # You might decide if a function can overwrite a variable or vice-versa, or if it's an error.
                # Current logic: if a variable was found and imported, we don't then import a function of the same name.
                # If both variable and function exist with the same name in the source module, variable takes precedence here.

            if not imported_successfully:
                raise Exception(f"Item '{item_name}' not found as variable or function in module '{path_raw}' (imported at line {ctx.start.line})")

        return None
    
    # Function definition: store signature and body
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

    # Return statement: throw exception
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

        elif ctx.getChildCount() == 2 and ctx.getChild(0).getText() in ('+', '-') and isinstance(ctx.factor(0), PySQLParser.FactorContext):
            op = ctx.getChild(0).getText()
            value = self.visit(ctx.factor(0))
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
                raise Exception(f"Undefined function '{fname}' at line {ctx.start.line}")
            
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

        elif ctx.ID():
            var_name = ctx.ID().getText()
            if var_name not in self.memory:
                raise Exception(f"Undefined variable '{var_name}' at line {ctx.start.line}")
            return self.memory[var_name]

        elif ctx.getChildCount() == 2 and ctx.getChild(0).getText() == 'not':
            val_to_negate = self.visit(ctx.factor(0))
            if not isinstance(val_to_negate, bool):
                raise Exception(f"'not' operator requires a boolean operand, got {self.infer_type(val_to_negate)} at line {ctx.start.line}")
            return not val_to_negate

        elif ctx.expr() and ctx.getChildCount() == 3 and \
             ctx.getChild(0).getText() == '(' and \
             isinstance(ctx.expr(0), PySQLParser.ExprContext) and \
             ctx.getChild(2).getText() == ')':
            return self.visit(ctx.expr(0))
        
        elif ctx.arrayLiteral():
            raise NotImplementedError(f"Array literal handling not fully implemented in visitFactor at line {ctx.start.line}")

        elif ctx.selectExpr():
            return self.visit(ctx.selectExpr(0))

        else:
            raise Exception(f"Invalid or unhandled factor structure near '{ctx.getText()}' at line {ctx.start.line}")
        
    
        if ctx.INT():
            return int(ctx.INT().getText())
        elif ctx.FLOAT():
            return float(ctx.FLOAT().getText())
        elif ctx.STRING():
            return ctx.STRING().getText()[1:-1]
        elif ctx.BOOL():
            return ctx.BOOL().getText().lower() == 'true'
        # elif ctx.ID() and not ctx.expr():
        elif ctx.ID() and ctx.getChildCount() == 1:
            var_name = ctx.ID().getText()
            if var_name not in self.memory:
                raise Exception(f"Undefined variable '{var_name}' at line {ctx.start.line}")
            return self.memory[var_name]
        elif ctx.getChildCount() == 2 and ctx.getChild(0).getText() == 'not':
            return not self.visit(ctx.factor())
        elif ctx.expr():
            return self.visit(ctx.expr())
        elif ctx.selectExpr():
            return self.visit(ctx.selectExpr())
        
        raise Exception(f"Invalid factor at line {ctx.start.line}")

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

        
# Error Handling
class PySQLErrorListener(ErrorListener):
    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        # Handle lexer errors (token recognition)
        if "token recognition error" in msg:
            # Get the raw input text
            input_stream = recognizer._input
            text = input_stream.strdata
            
            # Look for unclosed quotes
            quote_count = text.count('"')
            if quote_count % 2 != 0:
                # Find first unclosed quote
                last_quote = text.rfind('"')
                line_num = text[:last_quote].count('\n') + 1
                raise Exception(f"Unterminated string literal starting at line {line_num}")
            
        raise Exception(f"Syntax error at line {line}:{column} - {msg}")

    def reportError(self, recognizer, offendingSymbol, line, column, msg, e):
        # Forward to syntaxError for consistency
        self.syntaxError(recognizer, offendingSymbol, line, column, msg, e)

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
    except Exception as e:
        print(f"Error: {e}")


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


    

