hex_str = input("Paste the hexadecimal to be converted to binary (with spaces): ")
hexadecimal = []
binary = []
divider = []

for h in hex_str.split(" "):
    hexadecimal.append(h)
    divider.append("-------|")
    binary.append(format(int(h, 16), "0>8b"))

hexadecimal.reverse()
binary.reverse()
data = f"      {(" "*6).join(hexadecimal)}\n{"".join(divider)}\n{"".join(binary)}"

open("output.txt", "w").write(data)
