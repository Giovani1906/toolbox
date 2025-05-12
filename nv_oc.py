#!/usr/bin/env python

import pynvml

pynvml.nvmlInit()

# This sets the GPU to adjust - if this gives you errors, or you have multiple GPUs, set to 1 or try other values
my_gpu = pynvml.nvmlDeviceGetHandleByIndex(0)

# The GPU offset value should replace "240" in the line below.
pynvml.nvmlDeviceSetGpcClkVfOffset(my_gpu, 170)

# The Mem Offset should be **multiplied by 2** to replace the "3000" below
# For example, an offset of 500 in GWE means inserting a value of 1000 in the next line
pynvml.nvmlDeviceSetMemClkVfOffset(my_gpu, 800)

# The power limit should be set below in mW - 216W becomes 216000, etc.
# Remove the below line if you don't want to adjust power limits.
# pynvml.nvmlDeviceSetPowerManagementLimit(myGPU, 90000)
