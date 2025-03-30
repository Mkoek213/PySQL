# Generated from PySQL.g4 by ANTLR 4.13.1
from antlr4 import *
if "." in __name__:
    from .PySQLParser import PySQLParser
else:
    from PySQLParser import PySQLParser

# This class defines a complete generic visitor for a parse tree produced by PySQLParser.

class PySQLVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by PySQLParser#prog.
    def visitProg(self, ctx:PySQLParser.ProgContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PySQLParser#stat.
    def visitStat(self, ctx:PySQLParser.StatContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PySQLParser#assign.
    def visitAssign(self, ctx:PySQLParser.AssignContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PySQLParser#expr.
    def visitExpr(self, ctx:PySQLParser.ExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PySQLParser#printStat.
    def visitPrintStat(self, ctx:PySQLParser.PrintStatContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PySQLParser#ifStat.
    def visitIfStat(self, ctx:PySQLParser.IfStatContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PySQLParser#loopStat.
    def visitLoopStat(self, ctx:PySQLParser.LoopStatContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PySQLParser#funcDef.
    def visitFuncDef(self, ctx:PySQLParser.FuncDefContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PySQLParser#paramList.
    def visitParamList(self, ctx:PySQLParser.ParamListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PySQLParser#type.
    def visitType(self, ctx:PySQLParser.TypeContext):
        return self.visitChildren(ctx)



del PySQLParser