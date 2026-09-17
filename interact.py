import pexpect
import sys

child = pexpect.spawn('railway up --detach', encoding='utf-8')
child.expect('\? Select a service')
print("Saw prompt.")
# Send down arrow twice? Let's just print the whole buffer
print(child.before)
print(child.after)
# Send down arrow
child.sendline("\x1b[B")
child.sendline("\x1b[B")
child.sendline("\x1b[B")
# Or let's see what happens if we type "new"
child.sendline("covenant-backend")
child.sendeof()
print(child.read())
