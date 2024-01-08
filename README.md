# Trapy

Daniel Abad Fundora C311 

Anabel Banítez González C311 

Enzo Rojas D'Toste C311 

## ¿Cómo correrlo?

## Detalles de implementación

La clase PortManager es la encargada de gestionar puertos. Su propósito es llevar un registro en el archivo que se especifique ("./ports.json" por defecto) de los puertos que están siendo utilizados y proporcionar una interfaz para obtener, reservar y liberar puertos. Esta clase es útil para evitar conflictos de puertos.

La clase RecvTask es la encargada de recibir los mensajes de los clientes. Su propósito es recibir los mensajes de los clientes y procesarlos. Posee 3 metodos, 
     - init: inicializa la clase
     - stop: detiene la ejecución de la clase
     - _recv: metodo asincrono recibe los mensajes de los clientes hasta que la se llame al metodo stop()


La clase Conn representa una conexión de red entre un puerto origen y un puerto destino, posee los métodos:

      -  init: Inicializa la conexión, creando un socket raw con unos parametros por defecto
      -  get_time_limit: Duplica el tiempo de espera de la conexion e incrementa el contador de errors de temporizador
      -  reset_time_limit: Devuelve el tiempo de espera y el contador de errores de temporizador a sus valores por defecto
 
El método listen crea una conexion que acepta los paquetes entrantes a cierta dirección, esta clase recibe una dirección y crea una conexión, poniendole de parámetro de direccion fuente la dirección recibida

El método accept recibe una conexión previamente creada por el método listen y espera por una solicitud de conexión hacia la misma, para, si el paquete recibido cumple con todos los requisitos, aceptarla y enviar syn_ack, luego, si no recibe confirmación de que este fue recibido, envía otro, en otro caso, la conexión fue creada sin problemas. Este método puede tambien recibir un parámetro size que representa la maxima cantidad de paquetes que se puede recibir o enviar en la conexion, en caso de no recibirlo, se le asignará un valor por defecto.

El método dial crea una conexión con un destino, recibe una dirección y crea una conexión, poniendole de parámetro de direccion fuente la dirección recibida, envía un paquete de solicitud de conexión al destino, en caso de recibir syn_ack, se establece satisfactoriamente la conexión con la dirección de destino, en caso de que no se reciba nada en el límite de tiempo establecido en la conexión, se reenvía la solicitud y se duplica el tiempo de espera

El método send envía información desde un puerto origen a un puerto destino a través de una conexión, recibe una conexión y la información que se desea enviar, en caso de que la información sea mayor a 2^32 bytes, se divide la información en dos partes, se envía la primera parte y se espera a que se reciba un ack. Se inicializa una ventana deslizante tamaño 20 y se utiliza un protocolo de ventana deslizante. Se corre la ventana en dependencia del ACK recibido, que indicará el último bit que el receptor recibió satisfactoriamente. Si se recibe un paquete con el flag rst, se comienza a enviar desde el bit que este indica. El método devuelve un entero indicando la cantidad de bytes enviados

El método recv es el encargado de recibir la información enviada a través de una conexión, recibe una conexión y la longitud de la cantidad de datos a recibir y envia ack indicando el último paquete recibido satisfactoriamente. En caso de que se detecte la ausencia de un paquete, se envia rst y se indica elultimo paquete recibido satisfactoriamente. El método devulve los datos recibidos

El método close se encarga de recibir una conexión y cerrarla

El método parse_address recibe una dirección y devuelve el dispositivo y puerto que representa

El método build_packet se encarga de la construcción de un paquete de acuerdo a los datos correspondientes (direcciones de origen y destino, número de secuencia, información a enviar y los flags que representan los tipos especiales de paquetes )

El método get_checksum dado una informacion, calcula el checksum, para permitir la verificion de que los datos fueron enviados correctamente

El método get_packet, dado un paquete y una conexion devuelve el data, el IP Header y el TCP Heade

El método verify_checksum, dados los datos recibidos de un paquete, verifica si estos no están dañados comprobando si su checksum está bien calculado

El método clean_in_buffer se encarga de limpiar el imput buffer