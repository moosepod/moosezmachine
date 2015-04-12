"TEST main file"

<VERSION ZIP>
<CONSTANT RELEASEID 1>

"Main loop"

<CONSTANT GAME-BANNER
"TEST|
An interactive fiction by Matt Christensen">

<ROUTINE GO ()
    <CRLF> <CRLF>
    <TELL "Welcome!" CR CR>
    <V-VERSION> <CRLF>
    <SETG HERE ,THESTART>
    <MOVE ,PLAYER ,HERE>
    <V-LOOK>
    <REPEAT ()
        <COND (<PARSER>
                <PERFORM ,PRSA ,PRSO ,PRSI>
                <APPLY <GETP ,HERE ,P?ACTION> ,M-END>
                <OR <META-VERB?> <CLOCKER>>)>
        <SETG HERE <LOC ,WINNER>>>>

<INSERT-FILE "parser">

"Objects"

<OBJECT THESTART
    (IN ROOMS)
    (DESC "The first room")
    (FLAGS LIGHTBIT)>
