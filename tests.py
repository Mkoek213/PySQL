from io import StringIO
from contextlib import redirect_stdout
from PySQLInterpreter import run_interpreter  # Zmień 'your_module' na nazwę pliku z kodem bez .py

def test_case(description, code, expected_output):
    f = StringIO()
    with redirect_stdout(f):
        run_interpreter(code)
    output = f.getvalue().strip()
    print(f"✅ {description}: {'PASSED' if output == expected_output else 'FAILED'}")
    if output != expected_output:
        print(f"Expected: {expected_output}")
        print(f"Got:      {output}")
    print()

# -------------------------------
# 1. Deklaracja i przypisanie typu
test_case(
    "Deklaracja typu i poprawne przypisanie",
    "int a = 5\nprint(a)",
    "5"
)

# -------------------------------
# 2. Niedozwolone przypisanie typu
test_case(
    "Błąd: przypisanie złego typu (int → string)",
    "int x = 5\nx = \"hello\"\nprint(x)",
    "Error: Type mismatch on assignment to 'x' at line 2. Declared as int at line 1, assigned value of type string"
)

# -------------------------------
# 3. Operacje arytmetyczne + logiczne
test_case(
    "Wyrażenia arytmetyczno-logiczne",
    "bool ok = true\nint a = 10\nfloat b = 5.0\nprint((a > b) and ok)",
    "True"
)

# -------------------------------
# 4. If/else z działaniem
test_case(
    "Warunek if z else",
    "int n = 10\nif (n > 5) then print(\"big\") else print(\"small\")",
    "big"
)

# -------------------------------
# 5. Błąd: redeklaracja zmiennej
test_case(
    "Błąd: redeklaracja zmiennej",
    "int x = 5\nint x = 10\nprint(x)",
    "Error: Redeclaration of variable 'x' at line 2, originally declared at line 1"
)

# -------------------------------
# 6. Dzielenie intów zwraca int
test_case(
    "Dzielenie intów zwraca int",
    "print(5 / 2)",
    "2"
)

# -------------------------------
# 7. Obsługa unarnego plus
test_case(
    "Obsługa unarnego plus (5++3)",
    "print(5++3)",
    "8"
)

# -------------------------------
# 8. Obsługa unarnego plus przy zmiennych
test_case(
    "Obsługa unarnego plus na zmiennej",
    "int x = +10\nprint(+x)",
    "10"
)

# -------------------------------
# 9. Kombinacja unarnego plus i minus
test_case(
    "Kombinacja unarnego plus i minus (5+-3)",
    "print(5+-3)",
    "2"
)

# ================== IF-THEN-ELSE TESTS ==================

# Valid if-else with boolean condition
test_case(
    "IF: True condition with else",
    "if (true) then print(\"OK\") else print(\"FAIL\")",
    "OK"
)

test_case(
    "IF: False condition with else",
    "if (false) then print(\"FAIL\") else print(\"OK\")",
    "OK"
)

# If without else
test_case(
    "IF: No else branch (should print nothing)",
    "if (false) then print(\"FAIL\")",
    ""
)

# Type error in condition
test_case(
    "IF: Non-boolean condition error",
    "if (5) then print(\"FAIL\")",
    "Error: Condition must be a boolean, got <class 'int'> at line 1"
)

# ================== FUNCTION TESTS ==================

# 1. Simple valid function
test_case(
    "FUNC: Simple valid function",
    """func add(a:int,b:int) -> int exec (
    return a + b
)
int x = add(2,3)
print(x)""",
    "5"
)

# 2. Void function (no return, default None prints as 'None')
test_case(
    "FUNC: Void function",
    """func greet(a:string) -> void exec (
    print(a)
)
greet("Alice")""",
    "Alice"
)

# 3. Return–type mismatch
test_case(
    "FUNC: Return type mismatch",
    """func floatFunc() -> int exec (
    return 2.5
)
print(floatFunc())""",
    "Error: Function 'floatFunc' should return int, got float at line 4"
)

# 4. Wrong argument count
test_case(
    "FUNC: Arg count mismatch",
    """func foo(a:int) -> int exec (
    return a * 2
)
print(foo(1,2))""",
    "Error: Function 'foo' expects 1 args, got 2 at line 4"
)

# 5. Recursive function (factorial)
test_case(
    "FUNC: Recursive factorial",
    """func fact(n:int) -> int exec (
    if (n == 0) then
        return 1
    else
        return n * fact(n - 1)
)
print(fact(5))""",
    "120"
)

