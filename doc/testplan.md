1. créer un compte sur Alice (PinePhone)
1. créer un compte sur Bob (PinePhone)
1. ajouter Bob comme contact sur Alice
1. ajouter Alice comme contact sur Bob
1. Alice appelle Bob
    1. Bob accepte l'appel
        1. Alice raccroche
        1. Bob raccroche
        1. Alice met l'appel en attente
        1. Alice reprend l'appel
        1. Bob met l'appel en attente
        1. Bob reprend l'appel
    1. Bob refuse l'appel

# Create account
```
jamictrl.py --add-ring-account alice
account=$(jamictrl.py --get-all-accounts)
alice=$(jamictrl.py --get-account-details $account | awk '/Account.username/{print $2}')
```

# Start call
```
jamictrl.py --call $alice
```

# Wait for dring dring
```
call=$(jamictrl.py --get-call-list)
jamictrl.py --accept $call
jamictrl.py --hold $call
jamictrl.py --unhold $call
jamictrl.py --hangup $call
```
