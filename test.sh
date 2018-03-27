#!/bin/bash
set -eu

DATASTORE=$(mktemp)
dev_appserver.py app.yaml --datastore_path $DATASTORE &

for i in `seq 1 10`;do
    echo "Waiting for testserver to come up..."
    nc -w 1 localhost 8080 < /dev/null && break
    sleep 1
done
if [ "$i" == "30" ]; then
    echo "Test server did not start within 10 seconds."
    exit 1
fi

for inputfile in {create,escalate,escalate,close}.json
do
    curl -H 'Authorization: Basic dGluazp0aW5r' -d @examples/${inputfile} -H 'Content-type: application/json' http://localhost:8080/webhook/opsgenie
done

TEMPFILE=$(mktemp)
curl -H 'Authorization: Basic dGluazp0aW5r' -H 'Content-type: application/json' http://localhost:8080/metrics > $TEMPFILE
kill %1
wait %1

# Useful if changing output:
#cp $TEMPFILE examples/expected_output.txt
echo TEMPFILE: $TEMPFILE

# Poor man's assertion:
diff examples/expected_output.txt $TEMPFILE && echo "TESTS PASSED" || echo "TESTS FAILED"
rm $TEMPFILE
rm -fr $DATASTORE
