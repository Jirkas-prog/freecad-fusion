# FusionFlow – český návod

FusionFlow je nadstavba FreeCADu s ovládáním inspirovaným Fusionem. Přidává horní
pás nástrojů, překryvný browser, spodní historii, práci s oblastmi skic a stěnami,
vícetělesové odebírání, konstrukční geometrii a nástroje pro kontrolu modelu.
Výpočty nadále provádí FreeCAD. Jeho programové soubory se neupravují.

## Ověřená verze

**FreeCAD 1.1.3, Windows 11 x64, Python 3.11.14, Qt 6.8.3 / PySide6.**
Starší FreeCAD, Qt 5 a jiné systémy nejsou ověřené. Nadstavba není kompletní kopií
Fusionu a nepřidává podporu jeho souborového formátu F3D.

## Instalace

1. Nainstaluj [FreeCAD 1.1.3](https://github.com/FreeCAD/FreeCAD/releases/tag/1.1.3).
2. [Stáhni nadstavbu](https://github.com/Jirkas-prog/freecad-fusion/releases/latest/download/FusionFlow-addon.zip)
   a rozbal celý ZIP.
3. Ulož práci, zavři FreeCAD a spusť `Install.cmd`.
4. Spusť FreeCAD. Rozhraní se zapne automaticky. Po prvním spuštění jej ještě jednou
   restartuj, aby se uplatnilo celé téma OpenDark.

Instalátor kopíruje tři doplňky do `%APPDATA%\FreeCAD\v1-1\Mod`. Předchozí doplňky
a konfiguraci zálohuje do `FusionFlow-backups` vedle složky `Mod`. FreeCAD samotný
neinstaluje ani nepřepisuje. Pro ruční instalaci a vlastní profil viz hlavní README.

## Běžná práce

- Vyber rovinnou stěnu a klikni na **Create Sketch**, nebo začni skicu na základní rovině.
- Jednu skicu můžeš použít opakovaně: vyber uzavřenou oblast a stiskni **E**.
- **Extrude** podporuje také vybranou rovinnou stěnu, úkos a různé rozsahy vysunutí.
- Při **Cut** rozbal **Objects To Cut** a odškrtni tělesa, kterých se odebrání nemá týkat.
- **Join / Intersect** používají jedno cílové těleso; pro spojení více těles použij **Combine**.
- Konstrukční roviny jsou v **Construct**, řez modelem v **Inspect → Section Analysis**.
- Dole jsou ikony prvků historie. Název se ukáže při najetí, dvojklik otevře editaci.
- Browser lze přepínat mezi způsoby zobrazení. Složky Bodies a Sketches jsou přehled nad
  strukturou FreeCADu, nikoli změna významu jeho parametrických objektů.

Zkratky: **S** hledání, **L** lomená čára, **R** obdélník, **C** kružnice, **D** kóta,
**X** konstrukční geometrie, **T** oříznutí, **O** offset, **P** projekce, **M** přesun,
**I** měření. Prostřední tlačítko posouvá pohled, Shift + prostřední otáčí.

## Omezení a aktualizace

Historie vychází z existujících prvků dokumentu; neumí obnovit ztracenou historii
importovaného tělesa. Změna topologie může rozbít odkazy na hrany a plochy. Některé
analýzy používají vzorkování a slouží k orientační kontrole. Vlastní Python prvky
vyžadují nadstavbu i při pozdějším přepočtu modelu.

Novou verzi FreeCADu nejprve vyzkoušej v odděleném profilu. Pro návrat zavři FreeCAD,
přesuň doplňky mimo `Mod` a obnov zálohované soubory nastavení. Obnovení `user.cfg`
vrátí i další nastavení změněná od vytvoření zálohy.

[Úplný popis, struktura zdrojů a omezení](../README.md) · [Licence a původ součástí](../NOTICE.md)
