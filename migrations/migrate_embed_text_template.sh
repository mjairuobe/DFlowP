#!/bin/bash
# MongoDB-Migration für EmbedData text-Template Umstellung
#
# Dieses Script migriert alle bestehenden Embedding-Output-Datensätze,
# um den "text" Feld von gekürzt (first 500 chars) auf F-String-Template basiert zu ändern.
#
# Vorher: "text": "AI Trends in 2024. Machine Learning advances..."
# Nachher: "text": "{title} {summary}", "text_template": "{title} {summary}"
#
# Verwendung (aus dem Repository-Root):
#   chmod +x migrations/migrate_embed_text_template.sh
#   ./migrations/migrate_embed_text_template.sh
#   oder mit custom MongoDB URI:
#   MONGODB_URI="mongodb://user:pass@host:27017" ./migrations/migrate_embed_text_template.sh

set -e

# Konfiguration
MONGODB_URI="${MONGODB_URI:-mongodb://localhost:27017}"
DATABASE="dflowp"
COLLECTION="data_items"

# Standard Text-Template (sollte mit dflowp/plugin_embeddata/embed_data.py DEFAULT_TEXT_TEMPLATE übereinstimmen)
DEFAULT_TEXT_TEMPLATE="{title} {summary}"

echo "=========================================="
echo "EmbedData text-Template Migration"
echo "=========================================="
echo "MongoDB URI: $MONGODB_URI"
echo "Database: $DATABASE"
echo "Collection: $COLLECTION"
echo "Default Template: $DEFAULT_TEXT_TEMPLATE"
echo ""

# Verbindung testen
echo "Teste MongoDB-Verbindung..."
mongosh "$MONGODB_URI/$DATABASE" --eval "db.adminCommand('ping')" > /dev/null 2>&1 || {
    echo "ERROR: Kann nicht zu MongoDB verbinden!"
    echo "Stelle sicher, dass MongoDB läuft und die URI korrekt ist:"
    echo "  MONGODB_URI='$MONGODB_URI' ./migrations/migrate_embed_text_template.sh"
    exit 1
}
echo "✓ MongoDB-Verbindung erfolgreich"
echo ""

# Zähle betroffene Dokumente
echo "Analysiere Dokumente..."
AFFECTED=$(mongosh "$MONGODB_URI/$DATABASE" --quiet --eval "
db.getCollection('$COLLECTION').countDocuments({
    'doc_type': 'data',
    'content.embedding': { \$exists: true },
    'content.text_template': { \$exists: false }
})
" 2>/dev/null || echo "0")

if [ "$AFFECTED" = "0" ]; then
    echo "Keine zu migrierenden Dokumente gefunden."
    echo "Alle Embedding-Dokumente haben bereits text_template."
    exit 0
fi

echo "Gefunden: $AFFECTED Embedding-Datensätze zur Migration"
echo ""

# Backup-Information
echo "EMPFEHLUNG: Vor Migration ein Backup erstellen:"
echo "  mongodump --uri='$MONGODB_URI/$DATABASE' --out=./backup_before_text_template"
echo ""

# Migrierung durchführen
echo "Starte Migration..."
echo ""

# Update-Query in mongosh ausführen
mongosh "$MONGODB_URI/$DATABASE" << EOF
// Migriere alle Embedding-Dokumente: entferne alten "text" Feld und füge "text_template" hinzu
db.getCollection('$COLLECTION').updateMany(
    {
        'doc_type': 'data',
        'content.embedding': { \$exists: true },
        'content.text_template': { \$exists: false }
    },
    [
        {
            \$set: {
                // Speichere nur das Template (die "Bauanleitung")
                // Der Text wird bei Bedarf aus source_data_id + Template rekonstruiert
                'content.text_template': '$DEFAULT_TEXT_TEMPLATE'
            }
        },
        {
            \$unset: [
                // Entferne den alten gekürzen "text" Feld (first 500 chars)
                'content.text'
            ]
        }
    ]
)
EOF

echo ""
echo "=========================================="
echo "Migration abgeschlossen!"
echo "=========================================="
echo ""
echo "Verifikation:"
mongosh "$MONGODB_URI/$DATABASE" --quiet --eval "
const stats = db.getCollection('$COLLECTION').aggregate([
    { \\\$match: { 'doc_type': 'data', 'content.embedding': { \\\$exists: true } } },
    {
        \\\$group: {
            _id: null,
            total: { \\\$sum: 1 },
            with_template: {
                \\\$sum: { \\\$cond: [{ \\\$eq: [{ \\\$type: '\\\$content.text_template' }, 'string'] }, 1, 0] }
            }
        }
    }
]).next();

if (stats) {
    print('Embedding-Datensätze insgesamt: ' + stats.total);
    print('Mit text_template: ' + stats.with_template);
    print('Erfolgsquote: ' + Math.round(stats.with_template / stats.total * 100) + '%');
} else {
    print('Keine Embedding-Datensätze gefunden');
}
" 2>/dev/null

echo ""
echo "✓ Migration erfolgreich!"
echo ""
echo "Nächste Schritte:"
echo "1. Tests durchführen: pytest tests/process_test.py::test_embed_data_success -v"
echo "2. Daten verifizieren: mongosh dflowp"
echo "   db.data_items.findOne({'content.text_template': {'\$exists': true}})"
echo ""
echo "Text-Rekonstruktion (Beispiel):"
echo "   source_data_id: data_xxx"
echo "   text_template: {title} {summary}"
echo "   → db.data_items.findOne({'data_id': 'data_xxx'}) und Template auf content anwenden"
