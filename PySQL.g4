// Gramatyka dla ANTLR

grammar PySQL;

prog: (stat NEWLINE?)+ ;
NEWLINE: ('\r'? '\n')+ -> skip ;


stat:   assign          // Assignment
      | expr            // Expression
      | printStat       // Print Statement
      | ifStat          // If Statement
      | loopStat        // Loop Statement
      | funcDef         // Function Definition
      ;

assign: ID '=' expr ;

expr: INT
    | FLOAT
    | STRING
    | BOOL
    | ID
    | expr op=('+'|'-'|'*'|'/') expr
    | expr cmp=('>' | '<' | '>=' | '<=' | '==' | '!=') expr
    | '(' expr ')'
    | ID '(' (expr (',' expr)*)? ')'  // Poprawne wywołanie funkcji
    ;


PRINT: 'print' ;
printStat: PRINT '(' expr ')' ;

ifStat: 'if' '(' expr ')' 'then' (stat | printStat) ('else' (stat | printStat))? ;

loopStat: 'for' '(' ID 'in' '[' expr (',' expr)* ']' ')' 'do' stat 
        | 'while' '(' expr ')' 'do' stat ;

funcDef: 'func' '(' paramList? ')' '->' type 'exec' '(' stat+ ')' ;

paramList: ID ':' type (',' ID ':' type)* ;

type: 'int' | 'float' | 'string' | 'bool' ;

BOOL: 'true' | 'false' ;
ID: [a-zA-Z_][a-zA-Z_0-9]* ;

// np. '10text' oddzielało jako osobne tokeny
INVALID_NUMBER: [0-9]+ [a-zA-Z_]+ {raise Exception("Invalid number format: " + self.text)};
INT: [0-9]+ ;
FLOAT: [0-9]+'.'[0-9]+ ;
STRING: '"' ( '\\"' | ~["\n\r] )* '"'; // new string
// STRING: '"' .*? '"' ;
WS: [ \t]+ -> skip ;

