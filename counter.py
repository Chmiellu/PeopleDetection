import cv2
import os


def draw_rectangles(image, detected_objects):
    for i in range(detected_objects.shape[2]):
        confidence = detected_objects[0][0][i][2]
        if confidence > 0.3:
            class_index = int(detected_objects[0, 0, i, 1])
            if class_index == 15:
                height, width = image.shape[0], image.shape[1]

                upper_left_x = int(detected_objects[0, 0, i, 3] * width)
                upper_left_y = int(detected_objects[0, 0, i, 4] * height)
                lower_right_x = int(detected_objects[0, 0, i, 5] * width)
                lower_right_y = int(detected_objects[0, 0, i, 6] * height)

                cv2.rectangle(image, (upper_left_x, upper_left_y), (lower_right_x, lower_right_y), (0, 255, 0), 3)

def count_people(detected_objects):
    num_people = sum(1 for i in range(detected_objects.shape[2]) if int(detected_objects[0, 0, i, 1]) == 15)
    return num_people

def process_image(image_path):
    prototxt_path = 'model/MobileNetSSD_deploy.prototxt.txt'
    model_path = 'model/MobileNetSSD_deploy.caffemodel'

    net = cv2.dnn.readNetFromCaffe(prototxt_path, model_path)

    image = cv2.imread(image_path)
    blob = cv2.dnn.blobFromImage(cv2.resize(image, (300, 300)), 0.007, (300, 300), 130)

    net.setInput(blob)
    detected_objects = net.forward()

    draw_rectangles(image, detected_objects)

    output_image_path = os.path.join("uploaded_images", "marked_" + os.path.basename(image_path))
    cv2.imwrite(output_image_path, image)

    num_people = count_people(detected_objects)

    return num_people, output_image_path


