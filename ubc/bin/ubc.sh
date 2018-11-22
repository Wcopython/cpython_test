#!/bin/bash
#==================================
#FILE:ubc.sh
#  DESCRIPTION:--
#  OPTIONS:--
#  BUGS:--
#  NOTES:--
#  REVISON: 1.0.2
#  AUTHOR: FANG_SIR
#==================================

while true; do
	python /ubc/ubc/ubc.pyc &
	python /ubc/ntc/ntc_main.py
	sleep 5
	ps -ef | grep "python /ubc/ubc/ubc.pyc" | grep -v "grep" | awk '{print $2}' | xargs kill -9
	ps -ef | grep "python /ubc/ntc/ntc_main.py" | grep -v "grep" | awk '{print $2}' | xargs kill -9 
	echo 'has done one time'
    sleep 10
done

