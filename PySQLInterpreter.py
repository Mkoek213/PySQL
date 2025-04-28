from antlr4 import *
from antlr4.error.ErrorListener import ErrorListener
from PySQLLexer import PySQLLexer
from PySQLParser import PySQLParser
from PySQLVisitor import PySQLVisitor

class PySQLInterpreter(PySQLVisitor):
    def __init__(self):
        self.memory = {}
    
    def visitAssign(self, ctx):
        var_name = ctx.ID().getText()
        value = self.visit(ctx.expr())

        if value is None:
            raise Exception(f"Invalid value assigned to '{var_name}' at line {ctx.start.line}")
        
        self.memory[var_name] = value
        return value
    
    def visitLogicalExpr(self, ctx):
        left = self.visit(ctx.comparisonExpr(0))
        for i in range(1, len(ctx.comparisonExpr())):
            op = ctx.getChild(2*i-1).getText()
            right = self.visit(ctx.comparisonExpr(i))
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

    # tree = parser.prog()
    # interpreter = PySQLInterpreter()
    # interpreter.visit(tree)

    try:
        tree = parser.prog()
        interpreter = PySQLInterpreter()
        interpreter.visit(tree)
    except Exception as e:
        print(f"Error: {e}")
if __name__ == "__main__":
    test_programs_typy_logiczne = [
        ("Simple true/false", 'print(true)\nprint(false)'),
        ("Logic AND", 'print(true and true)\nprint(true and false)'),
        ("Logic OR", 'print(false or true)\nprint(false or false)'),
        ("Logic NOT", 'print(not true)\nprint(not false)'),
        ("Comparisons", 'print(5 > 3)\nprint(2 < 1)\nprint(5 == 5)\nprint(4 != 5)'),
        ("Complex Logic", 'print((5 > 3) and (2 < 5))\nprint(not (5 < 3))\nprint((1 == 1) or (2 != 2))'),
    ]
    test_programs_arithemtic = [
        ("Podstawowe operacje", [
            'print(2 + 3 * 4)',       # 14
            'print((2 + 3) * 4)',    # 20
            'print(10 / 3)',         # 3.333...
            'print(5.5 + 2.5)',      # 8.0
            'print(7 - 3.2)'         # 3.8
        ]),
        ("Mieszanie typów", [
            'print(5 + 3.14)',       # 8.14
            'print(2 * 1.5)',        # 3.0
            'print(10.0 / 2)'        # 5.0
        ]),
        ("Odwracanie liczb", [
            'x = 10\nprint(-x)',      # -10
            'print(-5.5)',            # -5.5
            'print(--10)'             # 10
        ]),
        ("Błędy", [
            'print(true * 5)',
            'print("text" + 5)',
            'print(-true)',
            'print(-"tekst")',
            'print(10 / 0)',
            'print(true * 5)',
            'print("text" + 5)'
        ])
    ]
        

for name, code in test_programs_typy_logiczne:
        print(f"\n=== Test TYPY LOGICZNE: {name} ===")
        run_interpreter(code)
        
for name, cases in test_programs_arithemtic:
    print(f"\n=== Test: {name} ===")
    for code in cases:
        print(f"\nInput: {code}")
        try:
            run_interpreter(code)
        except Exception as e:
            print(f"Error: {str(e)}")


