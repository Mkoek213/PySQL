from antlr4 import *
from antlr4.error.ErrorListener import ErrorListener
from PySQLLexer import PySQLLexer
from PySQLParser import PySQLParser
from PySQLVisitor import PySQLVisitor

class PySQLInterpreter(PySQLVisitor):
    def __init__(self):
        self.memory = {}
        self.var_types = {}  # Nazwa → (typ, linia)
    
    def visitAssign(self, ctx):
        var_name = ctx.ID().getText()
        value = self.visit(ctx.expr())
        line = ctx.start.line

        if value is None:
            raise Exception(f"Invalid value assigned to '{var_name}' at line {line}")

        value_type = self.infer_type(value)

        if var_name in self.var_types:
            declared_type, decl_line = self.var_types[var_name]
            if not self.type_matches(declared_type, value_type):
                raise Exception(f"Type mismatch on assignment to '{var_name}' at line {line}. Declared as {declared_type} at line {decl_line}, assigned value of type {value_type}")
        else:
            # Infer type if not declared yet
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
            
            # Tylko porównywalne typy (int/float) lub ten sam typ
            if type(left) != type(right):
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    pass  # OK: float vs int
                else:
                    raise Exception(f"Incompatible types for comparison '{op}' at line {ctx.start.line}")
            
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
            if not self.type_matches(declared_type, inferred_type):
                raise Exception(f"Type mismatch in declaration of '{var_name}' at line {line}: expected {declared_type}, got {inferred_type}")
        self.memory[var_name] = value
        self.var_types[var_name] = (declared_type, line)
        return value


    def visitFactor(self, ctx):
        if ctx.getChildCount() == 2 and ctx.getChild(0).getText() == '-':
        # Obsługa unarnego minusa
            value = self.visit(ctx.factor())
            if isinstance(value, bool):
                raise Exception(f"Invalid use of unary '-' with boolean value at line {ctx.start.line}")
            if isinstance(value, (int, float)):
                return -value
            else:
                raise Exception(f"Invalid type for unary '-' operator at line {ctx.start.line}")
    
        if ctx.INT():
            return int(ctx.INT().getText())
        elif ctx.FLOAT():
            return float(ctx.FLOAT().getText())
        elif ctx.STRING():
            return ctx.STRING().getText()[1:-1]
        elif ctx.BOOL():
            return ctx.BOOL().getText().lower() == 'true'
        elif ctx.ID() and not ctx.expr():
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

    # Ta metoda powinna być POZA apply_operator
    def check_numeric(self, left, right, line):
        if not (isinstance(left, (int, float)) and isinstance(right, (int, float))):
            raise Exception(f"Invalid types for arithmetic operation at line {line}")
        if isinstance(left, bool) or isinstance(right, bool):
            raise Exception(f"Boolean values cannot be used in arithmetic operations at line {line}")

    def visitPrintStat(self, ctx):
        value = self.visit(ctx.expr())
        print(value)
        return value

    def visitIfStat(self, ctx):
        condition = self.visit(ctx.expr())
        if condition:
            return self.visit(ctx.stat(0))
        elif ctx.stat(1):
            return self.visit(ctx.stat(1))
        return None

    def visitLoopStat(self, ctx):
        if ctx.getChild(0).getText() == "for":
            var_name = ctx.ID().getText()
            values = [self.visit(e) for e in ctx.expr()]
            for val in values:
                self.memory[var_name] = val
                self.visit(ctx.stat())
        elif ctx.getChild(0).getText() == "while":
            while self.visit(ctx.expr()):
                self.visit(ctx.stat())
        return None
    

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

def run_interpreter(input_code):
    lexer = PySQLLexer(InputStream(input_code))
    lexer.removeErrorListeners()
    lexer.addErrorListener(PySQLErrorListener())  # Added custom error listener (lexer)

    stream = CommonTokenStream(lexer)

    parser = PySQLParser(stream)
    parser.removeErrorListeners()
    parser.addErrorListener(PySQLErrorListener())  # Added custom error listener (parser)


    try:
        tree = parser.prog()
        interpreter = PySQLInterpreter()
        interpreter.visit(tree)
    except Exception as e:
        print(f"Error: {e}")    # tree = parser.prog()
    # interpreter = PySQLInterpreter()
    # interpreter.visit(tree)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python your_script.py <filename>")
        sys.exit(1)

    filename = sys.argv[1]
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            input_code = f.read()
        run_interpreter(input_code)
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

    

