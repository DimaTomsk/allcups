#!/usr/bin/env bash

RF_PATH="$(pwd)/reformat.py"

if [ "$ZIPPED" = True ]; then
    yes | unzip -n $MOUNT_POINT -d $SOLUTION_CODE_PATH
else
    yes | cp $MOUNT_POINT $SOLUTION_CODE_PATH/$SOLUTION_CODE_ENTRYPOINT
fi

if [ "$COMPILE" = True ]; then

    ERRORS="$(eval $COMPILE_COMMAND)"

    if [ $? -ne 0 ]; then
        echo "{\"status\": \"error\", \"message\": `echo "$ERRORS" | python3 $RF_PATH`, \"path_to_compiled_file\": \"\"}" > $COMPILE_LOG_LOCATION
    else
        echo "{\"status\": \"ok\", \"message\": \"compilation done\", \"path_to_compiled_file\": \"$COMPILED_FILE_PATH\"}" > $COMPILE_LOG_LOCATION
    fi

else
  eval "python3 -u ./main.py"
fi
