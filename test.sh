#!/bin/bash
set -eu

DATASTORE=$(mktemp)
dev_appserver.py --env_var PROMETHEUS_SCRAPE_PERIOD_SECONDS=1 app.yaml --datastore_path $DATASTORE &

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
    curl --silent -H 'Authorization: Basic bXl1c2VybmFtZTpteXBhc3N3b3Jk' -d @examples/${inputfile} -H 'Content-type: application/json' http://localhost:8080/webhook/opsgenie > /dev/null
done

TEMPFILE=$(mktemp)
curl --silent -H 'Authorization: Basic bXl1c2VybmFtZTpteXBhc3N3b3Jk' -H 'Content-type: application/json' http://localhost:8080/metrics > $TEMPFILE

# Useful if changing output:
#cp $TEMPFILE examples/expected_output_pre.txt
echo TEMPFILE: $TEMPFILE
# Poor man's assertion:
diff examples/expected_output_pre.txt $TEMPFILE && echo "TESTS PASSED" || echo "TESTS FAILED"
rm $TEMPFILE

sleep 6

TEMPFILE=$(mktemp)
curl --silent -H 'Authorization: Basic bXl1c2VybmFtZTpteXBhc3N3b3Jk' -H 'Content-type: application/json' http://localhost:8080/metrics > /dev/null
curl --silent -H 'Authorization: Basic bXl1c2VybmFtZTpteXBhc3N3b3Jk' -H 'Content-type: application/json' http://localhost:8080/metrics > $TEMPFILE
kill %1
wait %1

# Useful if changing output:
#cp $TEMPFILE examples/expected_output.txt
echo TEMPFILE: $TEMPFILE
# Poor man's assertion:
diff examples/expected_output.txt $TEMPFILE && echo "TESTS PASSED" || echo "TESTS FAILED"
rm $TEMPFILE

rm -fr $DATASTORE
