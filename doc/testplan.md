1. créer un compte sur Alice (pinephone)
1. créer un compte sur Bob (pinephone)
1. ajouter bob comme contact sur alice
1. ajouter alice comme contact sur bob
1. alice appelle bob
    1. bob accepte l'appel
        1. alice raccroche
        1. bob raccroche
        1. alice met l'appel en attente
        1. alice reprend l'appel
        1. bob met l'appel en attente
        1. bob reprend l'appel
    1. bob refuse l'appel

# create an account
```
jamictrl.py --add-ring-account alice
account=$(jamictrl.py --get-all-accounts)
alice=$(jamictrl.py --get-account-details $account | awk '/Account.username/{print $2}')
```

# make a call
```
jamictrl.py --call $alice
```

# wait for dring dring
```
call=$(jamictrl.py --get-call-list)
jamictrl.py --accept $call
jamictrl.py --hold $call
jamictrl.py --unhold $call
jamictrl.py --hangup $call
```
