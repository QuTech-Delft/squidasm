for file in *; do
    [[ ${file: -3} == ".py" ]] || continue
    # echo $file
    log_file=${file%.py}.log
    # echo $log_file

    python $file 1>$log_file 2>&1 
done
