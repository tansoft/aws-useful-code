<?php
function stringPickup(&$str, $begin, $end = '', $repl = true, $recursive = false, $offset = 0)
{
    $slen = strlen($begin);
    if ($slen == 0) {
        $spos = 0;
    } else {
        $spos = strpos($str, $begin, $offset);
    }
    if (false === $spos) {
        return false;
    }
    if ($end == '') {
        $epos = strlen($str);
    } else {
        $epos = strpos($str, $end, $spos+$slen);
    }
    if (false === $epos) {
        return false;
    }
    $ret = substr($str, $spos+$slen, $epos-$spos-$slen);
    if ($repl === true) {
        $replace = '';
    } else if ($repl === false) {
        $replace = $begin.$ret.$end;
    } else if ($repl === 'array'){
        $replace = $begin.$ret.$end;
        $ret = array($ret);
    } else {
        $replace = call_user_func_array($repl, array($ret, $begin, $end, $spos+$slen));
    }
    $nextpos = strlen($replace) + $spos;
    $str = substr($str, 0, $spos).$replace.substr($str, $epos + strlen($end));
    if ($recursive) {
        $subret = stringPickup($str, $begin, $end, $repl, $recursive, $nextpos);
        if ($repl === 'array') {
            if ($subret === false) {
                return $ret;
            }
            return array_merge($ret, $subret);
        }
        return true;
    }
    return $ret;
}
$data=file_get_contents("logs.txt");
$infos = [];
while(true) {
    $part = stringPickup($data, 'job:', 'mediaconvert finish');
    if ($part === false) break;
    # remove PROGRESSING
    stringPickup($part, '[', "PROGRESSING\n", true, true);
    # remove waiting lines
    stringPickup($part, "waiting", "...\n", true, true);
    # job:vmaf,id:1661013049531-w4csfm
    $line1 = stringPickup($part, '', "\n");
    # usetime:52,status:COMPLETE
    $line2 = stringPickup($part, '', "\n");
    $mode = stringPickup($line1, '', ',');
    $info['usetime']=stringPickup($line2, 'usetime:', ',');
    $info['status']=stringPickup($line2, 'status:', '');
    $info['files'] = [];
    while(true) {
        $sizeandfile=stringPickup($part, '', "\n");
        if ($sizeandfile === false) break;
        $vmaf=stringPickup($part, '', "\n");
        # remove date
        stringPickup($sizeandfile, '', ' ');
        # remove time
        stringPickup($sizeandfile, '', ' ');
        $sizeandfile = ltrim($sizeandfile, ' ');
        $size = stringPickup($sizeandfile, '', ' ');
        $file = ltrim($sizeandfile);
        $avmaf = stringPickup($vmaf, '(arithmetic mean): ', ' ');
        $hvmaf = stringPickup($vmaf, '(harmonic mean): ');
        $info['files'][$file] = ['size'=>$size, 'avmaf'=>$avmaf, 'hvmaf'=>$hvmaf];
    }
    $infos[$mode] = $info;
}
echo(json_encode($infos));