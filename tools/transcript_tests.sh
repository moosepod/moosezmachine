# Test CZECH.
CZECH_LOCATION="localtestdata/"
TRANSCRIPT="/tmp/gamelog.log"

python3 debug.py --file "$CZECH_LOCATION/czech.z3" --transcript /tmp/gamelog.log
diff --strip-trailing-cr --text $TRANSCRIPT "$CZECH_LOCATION/czech.out3"