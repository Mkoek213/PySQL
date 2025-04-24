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
    
    def visitExpr(self, ctx):
        if ctx.INT():
            return int(ctx.INT().getText())
        elif ctx.FLOAT():
            return float(ctx.FLOAT().getText())
        elif ctx.STRING():
            try:
                return ctx.STRING().getText()[1:-1]  # Remove quotes
            except:
                raise Exception(f"Malformed string at line {ctx.start.line}")
        elif ctx.BOOL():
            return ctx.BOOL().getText() == "true"
        elif ctx.ID():
            var_name = ctx.ID().getText()

            # Undefined variables
            if var_name not in self.memory:
                raise Exception(f"Undefined variable '{var_name}' at line {ctx.start.line}")
            
            return self.memory.get(var_name, None)
        
        elif ctx.op:  # Arithmetic operations
            left = self.visit(ctx.expr(0))
            right = self.visit(ctx.expr(1))

            # Division by 0
            if ctx.op.text == '/' and right == 0:
                raise Exception("Division by zero")
            
            # can add only same types
            if ctx.op.text == '+' and (type(left) != type(right)):
                raise Exception(f"Type mismatch: {type(left)} + {type(right)} at line {ctx.start.line}")

            if ctx.op.text == '+': return left + right
            if ctx.op.text == '-': return left - right
            if ctx.op.text == '*': return left * right
            if ctx.op.text == '/': return left / right
        elif ctx.cmp:  # Comparison operations
            left = self.visit(ctx.expr(0))
            right = self.visit(ctx.expr(1))
            if ctx.cmp.text == '>': return left > right
            if ctx.cmp.text == '<': return left < right
            if ctx.cmp.text == '>=': return left >= right
            if ctx.cmp.text == '<=': return left <= right
            if ctx.cmp.text == '==': return left == right
            if ctx.cmp.text == '!=': return left != right
        elif ctx.ID() and ctx.expr():  # Function call
            func_name = ctx.ID().getText()
            args = [self.visit(arg) for arg in ctx.expr()]
            return None  # Usuwamy obsługę print() tutaj
        
        raise Exception(f"Invalid expression at line {ctx.start.line}: {ctx.getText()}")
        # return None

    
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
    test_programs = [
        ("Hello World", '''print("Hello, World")'''),
        ("Zmienna i print", '''
x = "Hello"
print(x)
        '''),
        ("Dodawanie", '''
x = 10
y = 20
z = x + y
print(z)
        '''),
        ("Warunek IF", '''
x = 5
if (x > 3) then print("Yes") else print("No")
        '''),
        ("Pętla FOR", '''
for (i in [1, 2, 3]) do print(i)
        '''),
        ("Niezdefiniowana zmienna", '''
print(a)  
        '''),
        ("Błąd typu", '''
x = 5
y = "text"
z = x + y  
        '''),
        ("Dzielenie przez 0", '''
x = 10
y = 0
z = x / y  
        '''),
        ("Błędna składnia", '''
x = 10
y = 20
z = x +  
print(z)
        '''),
        ("Niezakończony string", '''
x = "Hello  
print(x)
        '''),
        ("Niezakończony string 2", '''
x = "text"
y = "text
print(x)
        ''')
    ]

additional_tests = [
("Porównania i bool", '''
a = 10
b = 20
c = a < b
print(c)
'''),

("Łączenie stringów", '''
first = "Hello"
second = "World"
print(first + second)
'''),

("Zagnieżdżony IF", '''
x = 10
if (x > 5) then
    if (x > 8) then print("Big") else print("Small")
'''),
("Nieprawidłowe wywołanie funkcji", '''
foobar(1, 2)
'''),

("Nieprawidłowa składnia warunku IF", '''
if x > 5 then print("bad syntax")
'''),

("Błędny zapis liczby (np. 123abc)", '''
x = 123abc
'''),

("Zmienna w pętli bez listy", '''
for (i in ) do print(i)
''')
]
test_programs.extend(additional_tests)
for name, code in test_programs:
        print(f"\n=== Test: {name} ===")
        run_interpreter(code)


