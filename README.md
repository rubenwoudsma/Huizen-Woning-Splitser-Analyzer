# Huizen Woning Splitser Analyzer

Dit project is ontstaan vanuit een eenvoudige maar fundamentele vraag:  
hoe kunnen we binnen een bestaande gemeente meer woonruimte creëren, zonder direct terug te vallen op grootschalige nieuwbouw?

In de gemeente Huizen is die vraag bijzonder relevant. De ruimte is beperkt, het dorpse karakter wordt gekoesterd en tegelijkertijd groeit de druk op de woningmarkt. De klassieke oplossingen – uitbreiden, verdichten, bouwen in het groen – liggen maatschappelijk en politiek gevoelig.

Daarom onderzoekt dit project een alternatief perspectief: het beter benutten van de bestaande woningvoorraad.

## Doel van het project

De Huizen Woning Splitser Analyzer is ontwikkeld om inzicht te geven in het zogenaamde ‘verborgen woningpotentieel’.  
Het richt zich op vragen als:

- Waar staan relatief grote woningen die mogelijk gesplitst kunnen worden?
- In welke buurten wonen relatief kleine huishoudens in grote huizen?
- Hoe verhoudt dit potentieel zich tot bestaande woningbouwplannen?
- Zijn we vooral aan het bouwen voor aantallen, of benutten we ook wat er al is?

Het doel is nadrukkelijk niet om exacte aantallen nieuwe woningen te voorspellen, maar om een onderbouwd en visueel inzicht te bieden dat het gesprek kan verrijken.

## Live applicatie

De interactieve applicatie is hier te bekijken:  
https://huizen-woning-splitser-analyzer.streamlit.app/

## Over de maker

Dit project is ontwikkeld door Ruben Woudsma:  
https://rubenwoudsma.nl

## Hoe werkt het?

De analyse combineert verschillende publieke databronnen:

- BAG (Basisregistratie Adressen en Gebouwen)  
  Voor locatie en oppervlakte van woningen

- CBS Wijk- en Buurtkaart  
  Voor ruimtelijke indeling en context

- Een indicatief model  
  Dat de kans inschat dat een woning wordt bewoond door een klein huishouden (maximaal twee personen)

- De zogenoemde ‘1.200-lijst’ van de gemeente  
  Met bestaande en geplande woningbouwinitiatieven

Deze bronnen worden samengebracht in een pipeline die de data verwerkt en vertaalt naar een interactieve kaart.

## Wat laat de applicatie zien?

De applicatie maakt drie dingen inzichtelijk:

1. Het splitsingspotentieel per buurt  
   Dit wordt weergegeven als een kleurverloop op de kaart

2. Individuele woningen  
   Met een indicatieve kans op splitsing

3. Bestaande bouwprojecten  
   Zodat zichtbaar wordt waar al plannen liggen

Daarnaast zijn er samenvattende indicatoren en grafieken opgenomen die helpen om patronen te herkennen.

## Belangrijke kanttekening

De uitkomsten van dit model zijn indicatief.

Er wordt gewerkt met publieke data en afgeleide aannames. Daardoor kan niet worden vastgesteld hoeveel bewoners er daadwerkelijk in een specifieke woning wonen, en ook niet of splitsing juridisch of praktisch mogelijk is.

De kracht van het model zit in het zichtbaar maken van patronen en potentieel, niet in het leveren van exacte plancapaciteit.

## Waarom is dit relevant?

In veel discussies over woningbouw ligt de nadruk op uitbreiding: waar kunnen we nog bouwen?

Dit project voegt daar een tweede perspectief aan toe:  
waar ligt al ruimte, maar benutten we die nog niet?

Door beide perspectieven naast elkaar te zetten ontstaat een completer beeld van de mogelijkheden binnen een gemeente.

## Gebruik voor andere gemeenten

Dit project is bewust zo opgezet dat het herbruikbaar is.

Wie het wil toepassen op een andere gemeente kan:

1. De repository forken
2. De gemeentefilter aanpassen in de pipeline
3. Eventueel lokale projecten toevoegen
4. De applicatie opnieuw deployen via Streamlit

## Technische opzet

- Python
- GeoPandas
- PDOK BAG API
- CBS Open Data
- Streamlit
- Folium

## Structuur

data/raw  
Bevat bronbestanden zoals CSV en Excel

data/processed  
Bevat gegenereerde datasets die in de applicatie worden gebruikt

pipeline.py  
Verwerkt en combineert de data

streamlit_app.py  
Visualiseert de resultaten

## Doorontwikkeling

Mogelijke vervolgstappen zijn:

- Verfijnen van het kansmodel met extra demografische data
- Scenario-analyse (bijvoorbeeld 5, 10 of 20 procent splitsing)
- Analyse van doorstroming
- Vergelijking tussen gemeenten

## Tot slot

Dit project is bedoeld als hulpmiddel om het gesprek over woningbouw te verdiepen.

Niet alleen de vraag: waar kunnen we bouwen?  
Maar ook: waar ligt al ruimte, en durven we die te benutten?
