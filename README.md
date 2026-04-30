# Huizen Woningsplitsing Analyzer

De Huizen Woningsplitsing Analyzer is een datagedreven tool die inzicht geeft in het **woningpotentieel binnen de bestaande woningvoorraad** van de gemeente Huizen en dit vergelijkt met geplande woningbouwprojecten.

🔗 Live applicatie:  
https://huizen-woning-splitser-analyzer.streamlit.app/

👤 Ontwikkeld door:  
https://rubenwoudsma.nl

---

## Aanleiding

De woningbouwopgave in Huizen is complex. De beschikbare ruimte is beperkt en tegelijkertijd is er een sterke wens om nieuwe woningen te realiseren voor lokale doelgroepen.

De discussie richt zich vaak op de vraag:

> Waar kunnen we nog bouwen?

Deze tool voegt daar een tweede perspectief aan toe:

> Waar zit al ruimte in de bestaande woningvoorraad?

---

## Doel van de applicatie

De applicatie heeft als doel om:

- inzicht te geven in **latente woningcapaciteit (woningsplitsing)**
- deze te vergelijken met **geplande woningbouw (1.200-lijst)**
- en dit te koppelen aan **leefbaarheid (klimaat / schaduw)**

De analyse is indicatief en bedoeld als ondersteuning voor beleidsvorming en ruimtelijke afwegingen.

---

## Gebruikte databronnen

De analyse combineert meerdere publieke databronnen:

### 1. BAG (Basisregistratie Adressen en Gebouwen)
Bron: PDOK  
https://www.pdok.nl/

- Locaties van verblijfsobjecten  
- Oppervlakte van woningen  
- Gebruiksdoelen  

Deze data wordt gebruikt om individuele woningen te analyseren.

---

### 2. CBS Wijk- en Buurtkaart
Bron: CBS Open Data  
https://www.cbs.nl/

- Buurt- en wijkgrenzen  
- Gemeentelijke indeling  

Wordt gebruikt om woningen ruimtelijk te koppelen aan buurten.

---

### 3. Klimaateffectatlas (schaduwdata)
Bron: Klimaateffectatlas  
https://www.klimaateffectatlas.nl/

- Schaduwpercentage per buurt  
- Afgeleid van landelijke klimaatscenario’s  

Deze data wordt gebruikt als **indicator voor hittestress en leefbaarheid**.

Let op: deze data valt onder een Creative Commons-licentie (CC-BY).  
Bronvermelding is verplicht bij gebruik.

---

### 4. 1.200-lijst (gemeente Huizen)

- Overzicht van geplande en onderzochte woningbouwprojecten  
- Samengesteld door gemeente, raad en participatieprocessen  

Deze lijst is handmatig opgeschoond en gegeocodeerd.

---

## Verwerking (pipeline)

De data wordt verwerkt via een Python pipeline (`pipeline.py`):

1. CBS buurten worden ingeladen en gefilterd op Huizen  
2. BAG-data wordt opgehaald via de PDOK API  
3. Woningen worden ruimtelijk gekoppeld aan buurten (spatial join)  
4. Een model berekent per woning een splitsingskans  
5. Potentieel wordt geaggregeerd per buurt  
6. Klimaatdata (schaduw) wordt toegevoegd per buurt  
7. De 1.200-lijst wordt ingelezen en gegeocodeerd  
8. Resultaten worden opgeslagen als GeoJSON en CSV  

De pipeline is robuust opgezet en kan omgaan met:

- API fouten (retry-mechanisme)  
- ontbrekende data  
- variaties in bronbestanden  

---

## Wat laat de applicatie zien?

### Kaart

De kaart combineert drie lagen:

#### 🔴 Buurten
- Totaal potentieel voor extra woningen  
- Gebaseerd op aggregatie van individuele woningen  

#### 🔵 Woningen
- Individuele adressen  
- Met indicatieve kans op splitsing  

#### 🟣 Projecten
- Geplande woningbouw  
- Gebaseerd op de 1.200-lijst  

---

### Analyse

Per project wordt gekeken naar:

- het lokale splitsingspotentieel  
- de omvang van het project  
- de leefbaarheid (schaduw / hittestress)  

Dit resulteert in:

#### Gebruik (%)
Hoeveel van het lokale potentieel wordt benut

#### Overbelasting (x)
Hoeveel groter een project is dan het beschikbare potentieel

#### Klimaatcontext
Mate van schaduw (indicatie voor hittestress)

---

## Belangrijkste inzichten

De analyse laat zien dat:

- woningbouw zich niet altijd richt op buurten met het grootste potentieel  
- buurten met veel potentieel vaak relatief weinig benut worden  
- sommige projecten plaatsvinden in gebieden met beperkte schaduw (klimaatgevoelig)  

Daarmee ontstaat een belangrijk inzicht:

> De plekken waar ruimte is, de plekken waar gebouwd wordt en de plekken waar het prettig wonen is, vallen niet vanzelf samen.

---

## Beperkingen

- Model is indicatief en vereenvoudigd  
- Geen inzicht in huishoudgrootte per woning  
- Geen rekening met regelgeving of eigendom  
- Klimaatdata is een proxy (schaduw ≠ volledige hittestress)  

---

## Gebruik en hergebruik

Deze tool is reproduceerbaar voor andere gemeenten:

1. Fork de repository  
2. Pas de gemeentefilter aan  
3. Voeg lokale projectdata toe  
4. Deploy via Streamlit  

---

## Conclusie

De Huizen Woningsplitsing Analyzer laat zien dat de woningbouwopgave niet alleen gaat over uitbreiden, maar ook over beter benutten van wat er al is.

Het biedt een aanvullend perspectief op de vraag:

> Bouwen we op de juiste plekken, of laten we kansen liggen in de bestaande stad?
