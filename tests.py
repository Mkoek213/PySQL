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
