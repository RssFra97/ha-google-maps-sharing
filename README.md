# Google Maps (condivisione posizione) per Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories)
[![Validate](https://github.com/rssfra97/ha-google-maps-sharing/actions/workflows/validate.yaml/badge.svg)](https://github.com/rssfra97/ha-google-maps-sharing/actions/workflows/validate.yaml)

Integrazione personalizzata che porta in Home Assistant la posizione delle persone che condividono la loro posizione con te su **Google Maps**. Ogni persona diventa un `device_tracker` GPS da collegare a una Persona, usare sulla mappa e nelle automazioni.

*English summary at the [end of this page](#english-summary).*

## Perché esiste

Home Assistant aveva l'integrazione `google_maps`, ma è una piattaforma **legacy** (configurabile solo da YAML) e con la [deprecazione dei device tracker legacy](https://developers.home-assistant.io/blog/2026/04/20/legacy-device-tracker-deprecation) verrà **rimossa in Home Assistant 2027.5**. Aveva anche due limiti pratici:

- quando i cookie scadevano si fermava e non riprovava più fino al riavvio successivo;
- per rinnovare i cookie bisognava sostituire un file a mano e riavviare.

Questa integrazione è la sostituta moderna.

## Funzionalità

| | Vecchio `google_maps` | `google_maps_sharing` |
|---|---|---|
| Configurazione | YAML | Interfaccia (*Dispositivi e servizi*) |
| Supportata dopo HA 2027.5 | ❌ | ✅ |
| Cookie scaduti | si ferma in silenzio | avviso *Riautenticazione richiesta* e riquadro dove **incollare i nuovi cookie**, senza riavvio |
| Rinnovo dei cookie | no | **automatico** ogni 15 minuti, salvato su file |
| Google non risponde | si ferma | riprova da sola |
| Cookie `#HttpOnly_` (export di Firefox) | ignorati | letti correttamente |
| Rinominare il tracker | no | sì |
| Sensore di stato della sessione | no | `binary_sensor` *problema* con dettagli |

## Requisiti

- Home Assistant **2024.12** o successivo.
- Un account Google con cui le persone da seguire condividono la posizione (vedi [Preparare l'account Google](#1-preparare-laccount-google)).
- Un browser per esportare i cookie: consigliato **Firefox** con l'estensione [cookies.txt](https://addons.mozilla.org/firefox/addon/cookies-txt/).

## Installazione

### Con HACS (consigliata)

1. In HACS apri il menu **⋮ → Repository personalizzati**.
2. Aggiungi `https://github.com/rssfra97/ha-google-maps-sharing` con categoria **Integrazione**.
3. Cerca **Google Maps (condivisione posizione)**, installala e **riavvia Home Assistant**.

### Manuale

1. Scarica l'ultima release.
2. Copia la cartella `custom_components/google_maps_sharing` nella cartella `custom_components` della configurazione di Home Assistant (quella che contiene `configuration.yaml`).
3. Riavvia Home Assistant.

## Configurazione

### 1. Preparare l'account Google

Il metodo più affidabile è un **account Google dedicato a Home Assistant**, che non usi da nessun'altra parte:

1. Crea un nuovo account Google (es. `casa.homeassistant@gmail.com`).
2. Dal telefono di ogni persona da seguire: *Google Maps → foto del profilo → Condivisione della posizione → Nuova condivisione* → scegli l'account dedicato → **Finché non disattivi**.
3. Accedi una volta a [maps.google.com](https://maps.google.com) con l'account dedicato e accetta le condivisioni ricevute.

Puoi usare anche il tuo account personale, ma la sessione scade più facilmente, perché la usi anche su telefono e PC.

### 2. Esportare i cookie

I cookie sono la "chiave" con cui l'integrazione legge Google Maps al posto tuo.

1. Apri una **finestra privata di Firefox** e abilita l'estensione *cookies.txt* per le finestre private (*Gestione componenti aggiuntivi → cookies.txt → Esegui nelle finestre anonime*).
2. **Disattiva eventuali VPN**: esporta dalla stessa rete da cui si collega Home Assistant.
3. Accedi con l'account Google al punto 1 e apri [maps.google.com](https://maps.google.com).
4. Clicca l'icona di *cookies.txt* → **Current Site** (o *All Sites*: l'integrazione tiene solo i cookie Google).
5. **Chiudi la finestra privata senza fare *Esci***: uscire dall'account annullerebbe subito la sessione.

> **Perché Firefox e non Chrome?** Le versioni recenti di Chrome legano la sessione Google al computer (*Device Bound Session Credentials*): i cookie copiati altrove smettono di funzionare dopo poco. Anche i cookie presi dal profilo del browser che usi ogni giorno durano poco, perché il browser continua a rinnovare quella sessione.

### 3. Aggiungere l'integrazione

1. *Impostazioni → Dispositivi e servizi → Aggiungi integrazione* → **Google Maps (condivisione posizione)**.
2. Compila:
   - **Account Google (email)**: l'account del punto 1.
   - **Cookie**: incolla **tutto il contenuto** del file `cookies.txt` esportato.
3. Conferma. L'integrazione verifica subito i cookie con Google e li salva.

Se il campo *Cookie* resta vuoto, l'integrazione usa il file dei cookie già presente oppure, se esiste, quello del vecchio `google_maps` (`.google_maps_location_sharing.cookies.<account>`): comodo per migrare.

### 4. Opzioni

*Dispositivi e servizi → Google Maps (condivisione posizione) → Configura*:

| Opzione | Predefinito | Descrizione |
|---|---|---|
| Intervallo di aggiornamento | 60 s | Ogni quanto leggere le posizioni (30–900 s). |
| Precisione minima | 200 m | Le posizioni meno precise vengono scartate e il tracker resta sull'ultima posizione buona. Vedi [Zone vicine](#zone-vicine-e-precisione). |
| Rinnova automaticamente i cookie | attivo | Chiede a Google di rinnovare la sessione ogni 15 minuti e salva i cookie aggiornati. |

## Entità create

### Un `device_tracker` per persona

Per ogni persona che condivide la posizione nasce un tracker GPS, per esempio `device_tracker.mario_rossi`, che puoi rinominare liberamente.

| Attributo | Contenuto |
|---|---|
| `latitude`, `longitude`, `gps_accuracy` | posizione e precisione in metri |
| `address` | indirizzo fornito da Google |
| `last_seen` | ora in cui il telefono ha inviato la posizione a Google |
| `battery_level`, `battery_charging` | batteria del telefono della persona |
| `full_name`, `nickname`, `id` | dati del profilo Google |

Il tracker è *non disponibile* quando Google non risponde oppure non è ancora arrivata nessuna posizione abbastanza precisa.

Viene creato anche un tracker per l'account usato per l'accesso, **disattivato di default** perché di solito non serve.

### `binary_sensor.google_maps_sessione`

Sensore di tipo *problema*: **OK** quando tutto funziona, **Problema** quando Google non risponde o i cookie non sono più validi.

| Attributo | Contenuto |
|---|---|
| `ultimo_errore` | motivo dell'ultimo errore |
| `ultimo_rinnovo_cookie` / `rinnovo_riuscito` | quando è stato fatto l'ultimo rinnovo e se Google l'ha accettato |
| `ultimo_salvataggio_cookie` | ultima scrittura del file dei cookie |
| `posizioni_google` | precisione e ora dell'ultima posizione di ogni persona, **anche se scartata** dal tracker |

## Collegare il tracker a una Persona

*Impostazioni → Persone → (persona) → Traccia dispositivi* → aggiungi il tracker di Google Maps.

Consiglio: aggiungi anche il tracker dell'**app Companion** della stessa persona. Home Assistant usa il dato più recente tra i due, quindi se Google Maps si blocca la persona continua a essere aggiornata.

## Come funziona il rinnovo automatico dei cookie

Nel browser la sessione Google resta valida perché il browser chiede periodicamente a Google di rinnovare il cookie `__Secure-1PSIDTS`. L'integrazione fa lo stesso: ogni 15 minuti invia la stessa richiesta (`accounts.google.com/RotateCookies`) e salva i nuovi cookie nel file `.google_maps_sharing.cookies.<account>`, nella cartella di configurazione. Dopo un riavvio riparte dai cookie aggiornati.

Puoi verificare che funzioni dagli attributi `ultimo_rinnovo_cookie` e `rinnovo_riuscito` del sensore della sessione.

> Google non documenta questo meccanismo, quindi non c'è garanzia che la sessione duri per sempre: se scade comunque, vedi la sezione successiva.

## Quando i cookie scadono

1. Il sensore della sessione passa a **Problema** e in *Impostazioni* compare **Riautenticazione richiesta**.
2. Clicca **Riconfigura**, [esporta nuovi cookie](#2-esportare-i-cookie) e incollali nel riquadro.
3. Conferma: l'integrazione si ricarica da sola, **senza riavviare** Home Assistant.

### Automazione di avviso (consigliata)

Ti manda una notifica sul telefono se la sessione ha un problema o se la posizione non si aggiorna da 3 ore. Sostituisci il tracker e il servizio di notifica con i tuoi.

```yaml
alias: Avviso Google Maps bloccato
mode: single
triggers:
  - trigger: template
    value_template: &blocco >
      {% set g = 'device_tracker.mario_rossi' %}
      {% set s = states[g] %}
      {% set seen = state_attr(g, 'last_seen') %}
      {{ is_state('binary_sensor.google_maps_sessione', 'on')
         or (seen is not none and (now() - as_datetime(seen)) > timedelta(hours=3))
         or (s is not none and s.state in ['unavailable', 'unknown']
             and (now() - s.last_changed) > timedelta(hours=3)) }}
    for: "00:10:00"
  - trigger: homeassistant
    event: start
conditions:
  - condition: template
    value_template: *blocco
actions:
  - delay: "00:05:00"
  - condition: template
    value_template: *blocco
  - action: notify.mobile_app_il_tuo_telefono
    data:
      title: Google Maps bloccato
      message: >
        {% if is_state('binary_sensor.google_maps_sessione', 'on') %}
        Sessione Google non valida: apri Home Assistant e incolla i nuovi cookie.
        {% else %}
        La posizione condivisa non si aggiorna: controlla Google Maps sul telefono.
        {% endif %}
```

## Migrare dal vecchio `google_maps`

1. Installa questa integrazione e aggiungila lasciando vuoto il campo *Cookie*: verranno importati quelli del vecchio file.
2. Nelle Persone sostituisci il vecchio `device_tracker.google_maps_<numero>` con il nuovo tracker.
3. Aggiorna automazioni e dashboard che usavano il vecchio tracker.
4. Commenta o rimuovi da `configuration.yaml` (o dal tuo package) il blocco:
   ```yaml
   device_tracker:
     - platform: google_maps
       username: ...
   ```
5. In `known_devices.yaml` imposta `track: false` sulle voci `google_maps_...` e riavvia.

Non tenere attive insieme le due integrazioni sullo stesso account: il rinnovo automatico cambia la sessione e il vecchio `google_maps` smetterebbe di funzionare.

## Zone vicine e precisione

Home Assistant assegna a un tracker la zona **più piccola** tra quelle che contengono la posizione, tenendo conto dell'imprecisione (`distanza dal centro − raggio < precisione`).

Esempio: zona *Casa* di 50 m e zona *Vicino* di 30 m a 80 m di distanza. Una posizione presa in casa con precisione 100 m "contiene" entrambe le zone e Home Assistant sceglie *Vicino* perché è più piccola. Il risultato è un falso "entrato in zona".

Rimedi:
- abbassa **Precisione minima** (per esempio 50 m) per scartare le posizioni imprecise;
- imposta lo stesso limite nell'app Companion (*Gestisci sensori → Posizione in background → Precisione minima*);
- nelle automazioni sui cambi di zona usa `for: "00:02:00"` per ignorare i salti isolati.

Dentro casa Google dà spesso una precisione di circa 100 m. Con un limite basso il tracker di Google può risultare *non disponibile* in casa: è normale, e la posizione la fornisce l'app Companion collegata alla stessa Persona.

## Risoluzione dei problemi

| Problema | Causa probabile e soluzione |
|---|---|
| *Cookie non validi o sessione scaduta* durante la configurazione | Cookie esportati dal profilo normale del browser, da Chrome o con la VPN attiva. Ripeti l'esportazione da una finestra privata di Firefox, senza VPN, senza fare *Esci*. |
| *Nessun cookie trovato* | Il campo è vuoto e non esiste un file dei cookie: incolla il contenuto di `cookies.txt`. |
| Il tracker non si muove e `last_seen` è vecchio | Il telefono non invia la posizione a Google. Sul telefono: condivisione della posizione attiva, Google Maps con batteria **senza restrizioni** e posizione **sempre consentita**. |
| Il tracker è *non disponibile* ma la sessione è OK | Le posizioni sono meno precise di *Precisione minima*: guarda `posizioni_google` nel sensore della sessione. |
| Nessun tracker creato | Nessuna condivisione attiva verso l'account, oppure condivisione non ancora accettata su maps.google.com. |
| `rinnovo_riuscito: false` | Google ha rifiutato il rinnovo: se la sessione resta OK non è grave; se scade, incolla nuovi cookie. |

Per un log dettagliato aggiungi a `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.google_maps_sharing: debug
```

## Privacy e sicurezza

- I cookie **equivalgono a un accesso al tuo account Google**. L'integrazione li salva in chiaro nella cartella di configurazione di Home Assistant (`.google_maps_sharing.cookies.<account>`), che finisce anche nei backup: proteggi i backup e non condividere mai il file.
- L'integrazione tiene solo i cookie dei domini Google e scarta gli altri.
- Un account dedicato limita i danni: se i cookie finissero in mani sbagliate, darebbero accesso solo all'account che vede le posizioni.
- I dati vengono letti solo da Google e restano in Home Assistant: nessun servizio di terze parti.

## Limitazioni

- Usa un'interfaccia **non ufficiale** di Google Maps: Google può cambiarla in qualsiasi momento e l'integrazione può smettere di funzionare.
- Il rinnovo automatico dei cookie si basa sul comportamento del browser e non è documentato da Google.
- L'aggiornamento della posizione dipende da quanto spesso il telefono la invia a Google: può essere più lento dell'app Companion.

## Crediti e licenza

- Lettura e parsing delle posizioni basati su [locationsharinglib](https://github.com/costastf/locationsharinglib) di Costas Tyfoxylos (MIT).
- Ispirata all'integrazione `google_maps` di [Home Assistant](https://github.com/home-assistant/core) (Apache 2.0).
- Rilasciata con licenza [MIT](LICENSE). Non affiliata a Google né a Home Assistant.

---

## English summary

**Google Maps (location sharing)** is a custom integration that replaces Home Assistant's legacy `google_maps` device tracker, which will be removed in Home Assistant 2027.5.

- **UI configuration**: add it from *Settings → Devices & services*, enter the Google account and paste the content of an exported `cookies.txt` (Firefox private window recommended, no VPN, close the window without signing out).
- **Automatic cookie renewal**: every 15 minutes it asks Google to rotate `__Secure-1PSIDTS`, the same way a browser does, and saves the updated cookies.
- **Re-authentication**: when the session expires, Home Assistant asks for new cookies, which you paste in a dialog. No file editing or restart needed.
- **Entities**: one GPS `device_tracker` per person sharing their location (address, last seen, battery), plus `binary_sensor.google_maps_sessione` (problem class) with error and renewal details.
- **Options**: update interval, minimum GPS accuracy, automatic cookie renewal.
- **Install** via HACS (custom repository, category *Integration*) or copy `custom_components/google_maps_sharing` and restart.

Cookies grant access to your Google account. Use a dedicated account and protect your backups. This integration relies on an unofficial Google API and may break without notice.
