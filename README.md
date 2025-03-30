# PySQL

## Docs
 - W pliku PySQL.g4 znajduje się gramatyka do parsera.

 - W pliku PySQLInterpreter.py znajduje się interpreter, wraz z przykładem użycia.

 - Komenda to kompilacji parsera to:
```bash
java -jar antlr-4.13.1-complete.jar -Dlanguage=Python3 -visitor PySQL.g4
```

 - Komenda do uruchomienia testów to:
```bash
python3 PySQLInterpreter.py
```

