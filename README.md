# Huizen Woningsplitsing Analyzer

De Huizen Woningsplitsing Analyzer is een datagedreven tool die inzicht geeft in het **splitsingspotentieel van bestaande woningen** binnen de gemeente Huizen, en dit vergelijkt met de geplande woningbouw uit de zogenoemde “1.200-lijst”.

🔗 Live applicatie:  
https://huizen-woning-splitser-analyzer.streamlit.app/

👤 Ontwikkeld door:  
https://rubenwoudsma.nl

---

## Aanleiding

De gemeente Huizen staat voor een complexe woningbouwopgave. De beschikbare ruimte is beperkt, terwijl de vraag naar woningen toeneemt. Tegelijkertijd is er maatschappelijke weerstand tegen grootschalige nieuwbouw, verdichting en aantasting van het dorpse karakter.

De huidige discussie richt zich vooral op:

> Waar kunnen we nog bouwen?

Dit project voegt daar een tweede perspectief aan toe:

> Waar zit al ruimte in de bestaande woningvoorraad?

---

## Doel van de applicatie

Deze tool heeft als doel om:

- inzicht te geven in **latent woningpotentieel** binnen bestaande wijken  
- dit potentieel te vergelijken met **geplande woningbouw**  
- zichtbaar te maken waar **beleidskeuzes en ruimtelijk potentieel niet op elkaar aansluiten**

Het model is nadrukkelijk indicatief en bedoeld als **ondersteuning voor beleidsanalyse en discussie**.

---

## Gebruikte databronnen

De analyse is volledig gebaseerd op publieke data en één aanvullende bron uit gemeentelijke besluitvorming.

### 1. BAG (Basisregistratie Adressen en Gebouwen)
Bron: PDOK API  
- Locaties van verblijfsobjecten  
- Oppervlakte per woning  
- Gebruiksdoelen (filter op wonen)

Deze dataset vormt de basis voor het identificeren van woningen.

---

### 2. CBS Wijk- en Buurtkaart
Bron: CBS Open Data  
- Buurt- en wijkgrenzen  
- Gemeentelijke indeling  

Wordt gebruikt om:
- woningen ruimtelijk te koppelen aan buurten  
- aggregaties per buurt te maken  

---

### 3. Modelmatige aannames (analyse-laag)

Omdat er geen openbare data beschikbaar is over huishoudgrootte per woning, wordt een indicatief model gebruikt:

- Grotere woningen → hogere kans op kleine huishoudens  
- Kleine huishoudens → grotere kans op splitsing  

Dit wordt vertaald naar:
- `p_le_2` → kans op huishoudens ≤ 2 personen  
- `expected_units_added` → verwacht splitsingspotentieel  

Belangrijk:
> Dit is een vereenvoudigd model en geen exacte weergave van de werkelijkheid.

---

### 4. 1.200-lijst (gemeente Huizen)

Bron: gemeenteraad / woonconferentie / participatie  
- Overzicht van bestaande en geplande woningbouwprojecten  
- Bevat o.a. locatie, aantal woningen en status  

Deze lijst is handmatig opgeschoond en verrijkt met coördinaten via geocoding.

---

## Verwerking (pipeline)

De data wordt verwerkt via een Python pipeline (`pipeline.py`):

1. CBS buurten worden ingeladen en gefilterd op Huizen  
2. BAG-data wordt opgehaald via de PDOK API  
3. Woningen worden ruimtelijk gekoppeld aan buurten (spatial join)  
4. Een model berekent per woning een splitsingskans  
5. Potentieel wordt geaggregeerd per buurt  
6. De 1.200-lijst wordt ingelezen, opgeschoond en gegeocodeerd  
7. Resultaten worden opgeslagen als GeoJSON en CSV  

---

## Wat laat de applicatie zien?

### Kaart (kern van de analyse)

De kaart combineert drie lagen:

#### 🔴 Buurten
- Tonen het totale splitsingspotentieel per buurt  
- Gebaseerd op aggregatie van individuele woningen  

#### 🔵 Woningen
- Individuele adressen  
- Met indicatieve kans op splitsing  

#### 🟣 Projecten
- Locaties uit de 1.200-lijst  
- Geplande woningbouw  

---

### Analyse: projecten vs potentieel

Voor elk project wordt gekeken:

- In welke buurt ligt het?  
- Hoe groot is het lokale splitsingspotentieel?  
- Hoe verhoudt dit zich tot de omvang van het project?  

Dit resulteert in drie categorieën:

- 🔴 Overbelast  
  → veel geplande woningen, weinig aanvullend potentieel  

- 🟢 Onderbenut  
  → veel potentieel, weinig plannen  

- 🟡 In balans  
  → plannen en potentieel liggen redelijk op één lijn  

---

## Interpretatie

De tool laat zien dat:

- woningbouw niet altijd plaatsvindt in buurten met het grootste potentieel  
- bestaande woningvoorraad een aanvullende rol kan spelen  
- er mogelijk sprake is van een mismatch tussen plannen en potentieel  

Belangrijk:

> Het model toont **technisch potentieel**, geen directe realisatiecapaciteit.

---

## Beperkingen

- Geen inzicht in werkelijke huishoudgrootte per woning  
- Geen rekening met regelgeving, eigendom of fysieke beperkingen  
- Geocoding van projectlocaties is indicatief  
- Model is vereenvoudigd en lineair  

---

## Gebruik voor andere gemeenten

Deze tool is reproduceerbaar:

1. Fork de repository  
2. Pas de gemeentefilter aan in de pipeline  
3. Voeg lokale projectdata toe  
4. Deploy via Streamlit  

---

## Conclusie

De Huizen Woningsplitsing Analyzer laat zien dat de woningbouwopgave niet alleen een kwestie is van uitbreiden, maar ook van beter benutten.

Het biedt een aanvullend perspectief op de vraag:

> Bouwen we op de juiste plekken, of laten we kansen liggen in de bestaande stad?
