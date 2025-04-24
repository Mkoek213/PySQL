grammar PySQL;

prog: (stat NEWLINE?)+ ;
NEWLINE: ('\r'? '\n')+ -> skip ;

stat:   assign
      | expr
      | printStat
      | ifStat
      | loopStat
      | funcDef
      ;

assign: ID '=' expr ;

expr: INT
    | FLOAT
    | STRING
    | BOOL
    | arrayLiteral                         // <--- nowy literał tablicowy
    | ID
    | expr op=('+'|'-'|'*'|'/') expr
    | expr cmp=('>' | '<' | '>=' | '<=' | '==' | '!=') expr
    | '(' expr ')'
    | ID '(' (expr (',' expr)*)? ')'       // wywołanie funkcji
    | ID '[' expr ']'                      // <--- dostęp do elementu tablicy
    ;

// Nowy literał tablicowy
arrayLiteral: '[' (expr (',' expr)*)? ']' ;

PRINT: 'print' ;
printStat: PRINT '(' expr ')' ;

ifStat: 'if' '(' expr ')' 'then' (stat | printStat) ('else' (stat | printStat))? ;

loopStat: 'for' '(' ID 'in' arrayLiteral ')' 'do' stat 
        | 'while' '(' expr ')' 'do' stat ;

funcDef: 'func' '(' paramList? ')' '->' type 'exec' '(' stat+ ')' ;

paramList: ID ':' type (',' ID ':' type)* ;

// Dodano typy tablicowe, w tym mieszane
type: 'int' 
    | 'float' 
    | 'string' 
    | 'bool' 
    | 'array' '<' type '>'                // np. array<int>, array<mixed>
    | 'mixed'                             // specjalny typ dla tablic mieszanych
    ;

BOOL: 'true' | 'false' ;
ID: [a-zA-Z_][a-zA-Z_0-9]* ;

INVALID_NUMBER: [0-9]+ [a-zA-Z_]+ {raise Exception("Invalid number format: " + self.text)};
INT: [0-9]+ ;
FLOAT: [0-9]+'.'[0-9]+ ;
STRING: '"' ( '\\"' | ~["\n\r] )* '"' ;
WS: [ \t]+ -> skip ;
