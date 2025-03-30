# Generated from PySQL.g4 by ANTLR 4.13.1
from antlr4 import *
if "." in __name__:
    from .PySQLParser import PySQLParser
else:
    from PySQLParser import PySQLParser

# This class defines a complete listener for a parse tree produced by PySQLParser.
class PySQLListener(ParseTreeListener):

    # Enter a parse tree produced by PySQLParser#prog.
    def enterProg(self, ctx:PySQLParser.ProgContext):
        pass

    # Exit a parse tree produced by PySQLParser#prog.
    def exitProg(self, ctx:PySQLParser.ProgContext):
        pass


    # Enter a parse tree produced by PySQLParser#stat.
    def enterStat(self, ctx:PySQLParser.StatContext):
        pass

    # Exit a parse tree produced by PySQLParser#stat.
    def exitStat(self, ctx:PySQLParser.StatContext):
        pass


    # Enter a parse tree produced by PySQLParser#assign.
    def enterAssign(self, ctx:PySQLParser.AssignContext):
        pass

    # Exit a parse tree produced by PySQLParser#assign.
    def exitAssign(self, ctx:PySQLParser.AssignContext):
        pass


    # Enter a parse tree produced by PySQLParser#expr.
    def enterExpr(self, ctx:PySQLParser.ExprContext):
        pass

    # Exit a parse tree produced by PySQLParser#expr.
    def exitExpr(self, ctx:PySQLParser.ExprContext):
        pass


    # Enter a parse tree produced by PySQLParser#printStat.
    def enterPrintStat(self, ctx:PySQLParser.PrintStatContext):
        pass

    # Exit a parse tree produced by PySQLParser#printStat.
    def exitPrintStat(self, ctx:PySQLParser.PrintStatContext):
        pass


    # Enter a parse tree produced by PySQLParser#ifStat.
    def enterIfStat(self, ctx:PySQLParser.IfStatContext):
        pass

    # Exit a parse tree produced by PySQLParser#ifStat.
    def exitIfStat(self, ctx:PySQLParser.IfStatContext):
        pass


    # Enter a parse tree produced by PySQLParser#loopStat.
    def enterLoopStat(self, ctx:PySQLParser.LoopStatContext):
        pass

    # Exit a parse tree produced by PySQLParser#loopStat.
    def exitLoopStat(self, ctx:PySQLParser.LoopStatContext):
        pass


    # Enter a parse tree produced by PySQLParser#funcDef.
    def enterFuncDef(self, ctx:PySQLParser.FuncDefContext):
        pass

    # Exit a parse tree produced by PySQLParser#funcDef.
    def exitFuncDef(self, ctx:PySQLParser.FuncDefContext):
        pass


    # Enter a parse tree produced by PySQLParser#paramList.
    def enterParamList(self, ctx:PySQLParser.ParamListContext):
        pass

    # Exit a parse tree produced by PySQLParser#paramList.
    def exitParamList(self, ctx:PySQLParser.ParamListContext):
        pass


    # Enter a parse tree produced by PySQLParser#type.
    def enterType(self, ctx:PySQLParser.TypeContext):
        pass

    # Exit a parse tree produced by PySQLParser#type.
    def exitType(self, ctx:PySQLParser.TypeContext):
        pass



del PySQLParser