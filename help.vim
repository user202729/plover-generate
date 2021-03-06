" Quickly copy entries from `errors.txt` file to `plover_ignore.py` (open them
" side by side in vim)
" Only vim is supported.
" Use `help.json` to quickly enter the key binds.

map \bo :rightbelow vsplit /tmp/errors.txt<cr><c-w><c-w>
" open the errors window

"the following key binds should be used when the focus is in the errors window 
map \bb "add<c-w><c-w>/^plover_briefs<cr>"ap<c-w><c-w>
" mark as brief
map \bt "add<c-w><c-w>/^plover_ortho_briefs<cr>"ap<c-w><c-w>
" mark as ortho brief
map \bm "add<c-w><c-w>/^plover_misstrokes<cr>"ap<c-w><c-w>
" mark as misstroke
map \bd "_dd<c-w><c-w><c-w><c-w>
" just delete
map \bu u<c-w><c-w>u<c-w><c-w>
" undo

