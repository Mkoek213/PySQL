
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
      | returnStat
      | breakStat
      | continueStat
      | importStat
      ;

identifierName: ID | INVALID_NUMBER ;
varDecl: varType identifierName ('=' expr)? ;
assign: (identifierName | arrayIndex) '=' expr ;
arrayIndex: identifierName '[' expr ']' ;

expr:   selectExpr
    |   assign
    |   logicalExpr
    ;

logicalExpr: comparisonExpr ( ('and' | 'or') comparisonExpr )* ;
comparisonExpr: addExpr ( ('>' | '<' | '>=' | '<=' | '==' | '!=' ) addExpr )* ;
addExpr: mulExpr ( ('+' | '-') mulExpr )* ;
mulExpr: factor ( ('*' | '/') factor )* ;
factor:
    '(' varType ')' factor
    | ('+' factor)
    | ('-' factor)
    | INT
    | FLOAT
    | STRING
    | BOOL
    | arrayLiteral
    | identifierName '(' exprList? ')'
    | identifierName
    | 'not' factor
    | '(' expr ')'
    | identifierName '[' expr ']'
    | parentAccess
    ;

parentAccess: ('parent::')+ identifierName ;

exprList: expr (',' expr)* ;

selectExpr:
    SELECT projection=expr FROM source=expr
    (WHERE condition=expr)?
    (ORDER BY (ASC | DESC))?
    ;

// Nowy literał tablicowy
arrayLiteral: '[' (expr (',' expr)*)? ']' ;

IMPORT: 'import';
PRINT: 'print' ;
printStat: PRINT '(' expr ')' ;

ifStat: 'if' '(' expr ')' 'then' (stat | printStat) ('else' (stat | printStat))? ;

loopStat
    : 'for' '(' forInitializer ';' expr? ';' forUpdate ')' 'do' block # ForLoop
    | 'while' '(' expr ')' 'do' block                                # WhileLoop
    ;

forInitializer: (varDecl | expr)? ; // Inicjalizator jest opcjonalny i może być deklaracją LUB wyrażeniem
forUpdate     : expr? ;             // Część aktualizująca jest opcjonalna i jest wyrażeniem

block: '{' stat* '}' ;

breakStat: 'break' ;
continueStat: 'continue' ;
importStat
    : 'import' STRING                                  # FullImport
    | 'from' STRING 'import' idList                    # SelectiveImport
    ;

// Define idList for comma-separated identifiers
idList: identifierName (',' identifierName)* ;

funcDef: 'func' identifierName '(' paramList? ')' '->' returnType 'exec' '(' stat+ ')' ;
returnStat: 'return' expr? ;

paramList: identifierName ':' varType (',' identifierName ':' varType)* ;

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

INVALID_NUMBER: [0-9]+ [a-zA-Z_]+;
INT: [0-9]+ ;
FLOAT: [0-9]+'.'[0-9]+ ;
STRING: '"' ( '\\"' | ~["\n\r] )* '"' ;
LINE_COMMENT: '//' ~[\r\n]* -> skip; // Matches '//' followed by any characters except newline
BLOCK_COMMENT: '/\\' .*? '/\\' -> skip; // Matches '/\*' then any char (non-greedy) until '\*/'
WS: [ \t]+ -> skip ;
