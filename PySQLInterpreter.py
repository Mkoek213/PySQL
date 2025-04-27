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
                return ctx.STRING().getText()[1:-1]
            except:
                raise Exception(f"Malformed string at line {ctx.start.line}")
        elif ctx.BOOL():
            return ctx.BOOL().getText() == "true"
        elif ctx.ID() and not ctx.expr():
            var_name = ctx.ID().getText()
            if var_name not in self.memory:
                raise Exception(f"Undefined variable '{var_name}' at line {ctx.start.line}")
            return self.memory.get(var_name, None)

        # NOT operator
        elif ctx.getChildCount() == 2 and ctx.getChild(0).getText() == 'not':
            value = self.visit(ctx.expr(0))
            return not value
        
        # Logical operations
        elif ctx.logic:
            left = self.visit(ctx.expr(0))
            right = self.visit(ctx.expr(1))
            if ctx.logic.text == 'and':
                return left and right
            elif ctx.logic.text == 'or':
                return left or right
        
        # Arithmetic operations
        elif ctx.op:
            left = self.visit(ctx.expr(0))
            right = self.visit(ctx.expr(1))
            if ctx.op.text == '/' and right == 0:
                raise Exception("Division by zero")
            if ctx.op.text == '+' and (type(left) != type(right)):
                raise Exception(f"Type mismatch: {type(left)} + {type(right)} at line {ctx.start.line}")
            if ctx.op.text == '+': return left + right
            if ctx.op.text == '-': return left - right
            if ctx.op.text == '*': return left * right
            if ctx.op.text == '/': return left / right
        
        # Comparison operations
        elif ctx.cmp:
            left = self.visit(ctx.expr(0))
            right = self.visit(ctx.expr(1))
            if ctx.cmp.text == '>': return left > right
            if ctx.cmp.text == '<': return left < right
            if ctx.cmp.text == '>=': return left >= right
            if ctx.cmp.text == '<=': return left <= right
            if ctx.cmp.text == '==': return left == right
            if ctx.cmp.text == '!=': return left != right
        
        elif ctx.ID() and ctx.expr():
            func_name = ctx.ID().getText()
            args = [self.visit(arg) for arg in ctx.expr()]
            return None
        
        # Parenthesized expression
        elif ctx.getChildCount() == 3 and ctx.getChild(0).getText() == '(' and ctx.getChild(2).getText() == ')':
            return self.visit(ctx.expr(0))

        
        raise Exception(f"Invalid expression at line {ctx.start.line}: {ctx.getText()}")


    
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
        

for name, code in test_programs_typy_logiczne:
        print(f"\n=== Test TYPY LOGICZNE: {name} ===")
        run_interpreter(code)


