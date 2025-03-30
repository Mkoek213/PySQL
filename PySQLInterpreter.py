from antlr4 import *
from PySQLLexer import PySQLLexer
from PySQLParser import PySQLParser
from PySQLVisitor import PySQLVisitor

class PySQLInterpreter(PySQLVisitor):
    def __init__(self):
        self.memory = {}
    
    def visitAssign(self, ctx):
        var_name = ctx.ID().getText()
        value = self.visit(ctx.expr())
        self.memory[var_name] = value
        return value
    
    def visitExpr(self, ctx):
        if ctx.INT():
            return int(ctx.INT().getText())
        elif ctx.FLOAT():
            return float(ctx.FLOAT().getText())
        elif ctx.STRING():
            return ctx.STRING().getText().strip('"')
        elif ctx.BOOL():
            return ctx.BOOL().getText() == "true"
        elif ctx.ID():
            var_name = ctx.ID().getText()
            return self.memory.get(var_name, None)
        elif ctx.op:  # Arithmetic operations
            left = self.visit(ctx.expr(0))
            right = self.visit(ctx.expr(1))
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

        return None

    
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

# Uruchamianie interpretera

def run_interpreter(input_code):
    lexer = PySQLLexer(InputStream(input_code))
    stream = CommonTokenStream(lexer)
    parser = PySQLParser(stream)
    tree = parser.prog()
    interpreter = PySQLInterpreter()
    interpreter.visit(tree)

if __name__ == "__main__":
    code = """
    x = 10
    print(x)
    """
    run_interpreter(code)