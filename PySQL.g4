grammar PySQL;

prog: (stat NEWLINE?)+ ;
NEWLINE: ('\r'? '\n')+ -> skip ;

stat:   varDecl
      | assign
      | expr
      | printStat
      | ifStat
      | loopStat
      | funcDef
      | returnStat // new
      | breakStat
      | continueStat
      | importStat 
      ;

varDecl: varType ID ('=' expr)? ;
assign: ID '=' expr ;

expr: logicalExpr;

logicalExpr: comparisonExpr ( ('and' | 'or') comparisonExpr )* ;
comparisonExpr: addExpr ( ('>' | '<' | '>=' | '<=' | '==' | '!=' ) addExpr )* ;
addExpr: mulExpr ( ('+' | '-') mulExpr )* ;
mulExpr: factor ( ('*' | '/') factor )* ;
factor:
    ('+' factor)
    | ('-' factor)
    | INT
    | FLOAT
    | STRING
    | BOOL
    | arrayLiteral
    | ID '(' exprList? ')'
    | ID
    | 'not' factor
    | '(' expr ')'
    | ID '[' expr ']'
    | selectExpr
    ;


exprList: expr (',' expr)* ;

selectExpr: SELECT expr FROM expr (WHERE expr)? (ORDER BY (ASC | DESC))? ;

// Nowy literał tablicowy
arrayLiteral: '[' (expr (',' expr)*)? ']' ;

IMPORT: 'import';
PRINT: 'print' ;
printStat: PRINT '(' expr ')' ;

ifStat: 'if' '(' expr ')' 'then' (stat | printStat) ('else' (stat | printStat))? ;

loopStat
    : 'for' '(' assign ';' expr ';' assign ')' 'do' block
    | 'while' '(' expr ')' 'do' block
    ;

block: '{' stat* '}' ;

breakStat: 'break' ;
continueStat: 'continue' ;
importStat: 'import' STRING ;




funcDef: 'func' ID '(' paramList? ')' '->' returnType 'exec' '(' stat+ ')' ;
returnStat: 'return' expr? ;

paramList: ID ':' varType (',' ID ':' varType)* ;

// Dodano typy tablicowe, w tym mieszane
returnType: varType | 'void' ;
varType: 'int'
    | 'float'
    | 'string'
    | 'bool'
    | 'array' '<' varType '>'                // np. array<int>, array<mixed>
    | 'mixed'                             // specjalny typ dla tablic mieszanych
    ;
    
SELECT: 'select' | 'SELECT';
FROM: 'from' | 'FROM';
WHERE: 'where' | 'WHERE';
ORDER: 'order' | 'ORDER';
BY: 'by' | 'BY';
ASC: 'asc' | 'ASC';
DESC: 'desc' | 'DESC';
BREAK: 'break' ;
CONTINUE: 'continue' ;


BOOL: 'true' | 'false' ;
ID: [a-zA-Z_][a-zA-Z_0-9]* ;

INVALID_NUMBER: [0-9]+ [a-zA-Z_]+ {raise Exception("Invalid number format: " + self.text)};
INT: [0-9]+ ;
FLOAT: [0-9]+'.'[0-9]+ ;
STRING: '"' ( '\\"' | ~["\n\r] )* '"' ;
WS: [ \t]+ -> skip ;
