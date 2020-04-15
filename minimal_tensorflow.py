import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

if __name__ == '__main__':

    model = tf.keras.Sequential([
    layers.Dense(64, activation='relu', input_shape=(32,)),
    layers.Dense(64, activation='relu'),
    layers.Dense(10)])

    model.compile(optimizer=tf.keras.optimizers.Adam(0.01),
                loss=tf.keras.losses.CategoricalCrossentropy(from_logits=True),
                metrics=['accuracy'])

    data = np.random.random((1000, 32))
    labels = np.random.random((1000, 10))

    model.fit(data, labels, epochs=10, batch_size=32)

    print('Success - exiting')