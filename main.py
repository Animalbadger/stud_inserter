from vision.detect import get_holes
#wazzup i cleaned up the whole envrioment for ya 
print("Starting detection test back up son")

holes = get_holes()

print("Holes found:")
for h in holes:
    print(h)