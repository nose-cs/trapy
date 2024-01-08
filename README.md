# Trapy

Daniel Abad Fundora C311 

Anabel Banítez González C311 

Enzo Rojas D'Toste C311 

## ¿Cómo ejecutarlo?

En el directorio ``trapy``, ejecutar el siguiente comando:
```
sudo python3 test.py --accept '<host>:<port>' --file <source-file-path>
```
son necesarios los permisos de administrador.

Y en otra terminal ejecutar:
```
sudo python3 test.py --dial '<host>:<port>' --file <destination-file-path>
```
host y port deben ser iguales.

## Detalles de implementación

La clase ``PortManager`` es la encargada de gestionar puertos. Su propósito es llevar un registro en el archivo que se especifique ("./ports.json" por defecto) de los puertos que están siendo utilizados y proporcionar una interfaz para obtener, reservar y liberar puertos. Esta clase es útil para evitar conflictos de puertos.

La clase ``RecvTask`` es la encargada de recibir los mensajes de los clientes. Su propósito es recibir los mensajes de los clientes y procesarlos. Posee 3 metodos, 
    
- stop: detiene la ejecución de la clase
- _recv: metodo asincrono recibe los mensajes de los clientes hasta que la se llame al metodo stop()

La clase Conn representa una conexión de red entre un puerto origen y un puerto destino, posee los métodos:
      
-  init: Inicializa la conexión, creando un socket raw con unos parametros por defecto
-  get_time_limit: Duplica el tiempo de espera de la conexion e incrementa el contador de errors de temporizador
-  reset_time_limit: Devuelve el tiempo de espera y el contador de errores de temporizador a sus valores por defecto
 
El método ``listen`` crea una conexion que acepta los paquetes entrantes a cierta dirección, esta clase recibe una dirección y crea una conexión, poniendole de parámetro de direccion fuente la dirección recibida

El método ``accept`` recibe una conexión previamente creada por el método listen y espera una solicitud de conexión. A continuación el paso a paso de lo que realiza:

- Espera de conexión: Entra en un bucle infinito donde establece el tiempo de espera del socket a None y espera recibir datos del socket.
- Recepción de datos: Intenta recibir datos del socket con un tamaño máximo de 1024 bytes. Si recibe datos correctamente, los desempaqueta para obtener las cabeceras IP y TCP.
- Verificación de bandera SYN: Verifica si el paquete TCP recibido tiene la bandera SYN establecida a 1, lo que indica una solicitud de inicio de conexión.
- Establecimiento de nueva conexión: Si la bandera SYN está presente, crea un nuevo objeto Conn para la nueva conexión y asigna las direcciones de origen y destino basadas en la dirección recibida y un nuevo puerto obtenido del PortManager.
- Envío de respuesta SYN-ACK: Construye un nuevo paquete TCP con la bandera SYN establecida y un número de secuencia, y lo envía al destino para completar el segundo paso del "three-way handshake" de TCP.
- Espera de ACK: Entra en otro bucle infinito donde espera recibir el ACK final del cliente para completar el proceso de establecimiento de la conexión.
- Cierre por tiempo de espera: Si se alcanza un límite de tiempo sin recibir el ACK, intenta reenviar el paquete SYN-ACK y, si aún así no se completa la conexión, reinicia el proceso de aceptación.
- Finalización del handshake: Si recibe el ACK correctamente, imprime un mensaje de éxito del handshake.
- Retorno del objeto de conexión: Finalmente se retorna el nuevo objeto ``Conn`` que representa la conexión aceptada.

El método ``dial`` se encarga de establecer una conexión con una dirección remota. La función dial toma como argumentos una dirección IP y un puerto (compuesto por la tupla address), y un tamaño de paquete size que es opcional y por defecto es 1024 bytes. A continuación, se describe paso a paso lo que realiza este método:
-  Creación del objeto de conexión (Conn): Se crea una instancia de Conn con el tamaño máximo de paquetes especificado.
-  Gestión de puertos: Se instancia un PortManager y se asigna una dirección de origen al objeto de conexión conn utilizando el puerto obtenido del PortManager y la dirección IP obtenida del socket de conn.
-  Construcción y envío de paquetes: Se construye un paquete inicial con un flag SYN (sincronización) y se envía a la dirección de destino utilizando el método sendto del socket.
-  Espera de respuesta y reenvío: El método entra en un bucle que espera una respuesta del destino. Si se sobrepasa el tiempo límite sin recibir respuesta, se reenvía el paquete SYN y se duplica el tiempo de espera. Si se recibe un paquete, se rompe el bucle.
-  Manejo de excepciones y tiempo de espera: Durante la espera, el método puede capturar excepciones de tiempo de espera y continuar esperando. Si se alcanza un tiempo límite sin éxito, se lanza una excepción ConnException.
-  Establecimiento de la conexión: Si se recibe una respuesta válida, se actualizan los números de secuencia y confirmación (seq y ack) y se envía un paquete de confirmación al destino.
-  Retorno del objeto de conexión: Finalmente, la función retorna el objeto de conexión ``conn`` que representa la conexión establecida.

El método ``send`` envía información desde un puerto origen a un puerto destino a través de una conexión, recibe una conexión y la información que se desea enviar, en caso de que la información sea mayor a 2^32 bytes, se divide la información en dos partes, se envía la primera parte y se espera a que se reciba un ack. Se inicializa una ventana deslizante tamaño 20 y se utiliza un protocolo de ventana deslizante. Se corre la ventana en dependencia del ACK recibido, que indicará el último bit que el receptor recibió satisfactoriamente. Si se recibe un paquete con el flag rst, se comienza a enviar desde el bit que este indica. El método devuelve un entero indicando la cantidad de bytes enviados

El método ``recv`` es el encargado de recibir la información enviada a través de una conexión, recibe una conexión y la longitud de la cantidad de datos a recibir y envia ack indicando el último paquete recibido satisfactoriamente. En caso de que se detecte la ausencia de un paquete, se envia rst y se indica elultimo paquete recibido satisfactoriamente. El método devulve los datos recibidos

El método ``close`` se encarga de recibir una conexión y cerrarla.

En ``utils.py`` encontramos las funciones siguientes:
- parse_address recibe una dirección y devuelve el dispositivo y puerto que representa
- build_packet se encarga de la construcción de un paquete de acuerdo a los datos correspondientes (direcciones de origen y destino, número de secuencia, información a enviar y los flags que representan los tipos especiales de paquetes )
- get_checksum dado una informacion, calcula el checksum, para permitir la verificion de que los datos fueron enviados correctamente
- get_packet, dado un paquete y una conexion devuelve el data, el IP Header y el TCP Heade
- verify_checksum, dados los datos recibidos de un paquete, verifica si estos no están dañados comprobando si su checksum está bien calculado
- clean_in_buffer se encarga de limpiar el imput buffer