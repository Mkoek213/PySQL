# Gramatyka dla ANTLR

grammar PySQL;

prog:   stat+ ;

stat:   assign          # Assignment
      | expr            # Expression
      | printStat       # Print Statement
      | ifStat          # If Statement
      | loopStat        # Loop Statement
      | funcDef         # Function Definition
      ;

assign: ID '=' expr ';' ;

expr:   INT             # Integer
      | FLOAT           # Float
      | STRING          # String
      | BOOL            # Boolean
      | ID              # Variable Reference
      | expr op=('+'|'-'|'*'|'/') expr  # Arithmetic
      | '(' expr ')'    # Parentheses
      ;

printStat: 'print' '(' expr ')' ';' ;

ifStat: 'if' '(' expr ')' 'then' stat ('else' stat)? ;

loopStat: 'for' '(' ID 'in' '[' expr (',' expr)* ']' ')' 'do' stat 
        | 'while' '(' expr ')' 'do' stat ;

funcDef: 'func' '(' paramList? ')' '->' type 'exec' '(' stat+ ')' ;

paramList: ID ':' type (',' ID ':' type)* ;

type: 'int' | 'float' | 'string' | 'bool' ;

BOOL: 'true' | 'false' ;
ID: [a-zA-Z_][a-zA-Z_0-9]* ;
INT: [0-9]+ ;
FLOAT: [0-9]+'.'[0-9]+ ;
STRING: '"' .*? '"' ;
WS: [ \t\r\n]+ -> skip ;