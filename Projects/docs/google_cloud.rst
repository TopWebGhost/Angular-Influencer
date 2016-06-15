Google Cloud
=========================

Google Compute Engine (GCE) is a cloud service (IaaS) similar to AWS. Unfortunately it doesn't support Ubuntu images (yet), so we have to either port our server infrastructure to Debian or prepare unofficial Ubuntu images.


Debian vs. Ubuntu for Worker Images
-----------------------------------

The ``user_data.sh`` and ``deploy.sh`` scripts support Debian installations to an extent, but do not install Firefox. Debian distros do not ship a real Firefox browser, but use their Iceweasel clone instead. We need to resort to hacks like using the Linux Mint repository (not supported by the install scripts yet).

We chose to build a custom Ubuntu 14.04 image, but, if needed, it shouldn't be horribly hard to switch to Debian.

RabbitMQ Cluster
----------------

The RabbitMQ cluster we run is installed using the default Google One-click deployments and runs on Debian. It has a single disk-based queue node and a bunch of memory-only nodes, all load-balanced behind a shared IP address.


Building Custom Ubuntu Images for GCE
-------------------------------------

This has been adapted from the `hagikuratakeshi`_ blog. It uses QEMU to install a Ubuntu image and then configures grub and kernel parameters for the KVM hypervisor used by GCE. The blog recommends installing QEMU from source, but the default Ubuntu 14.04 package just works.

.. _hagikuratakeshi: http://hagikuratakeshi.hatenablog.com/entry/2014/05/11/004412

.. note ::

	.. index ::
	   single: tools working on; docstrings

	The image we build here has only 10 GB of disk space. Make sure you go through the section about expanding it to larger sizes too!


1. Install QEMU on your host machine.

    ::

    $ sudo apt-get install qemu-system-x86 qemu-kvm qemu-utils

2. Download an Ubuntu Server install ISO image.
3. Create a 10 GB disk image:

    ::

    $ qemu-img create disk.raw 10g

This one is important. The disk image *must* be named disk.raw or GCE won't recognize our image archive later on.

4. Launch a QEMU VM, booting from a "cd-rom" using the Ubuntu ISO image (Remember to tweak the ISO path!):

    ::

    $ qemu-system-x86_64 --enable-kvm -smp 2 -m 3750m -net nic,model=virtio -net user,hostfwd=tcp::2222-:22 -device virtio-scsi-pci,id=scsi -device scsi-hd,drive=hd,physical_block_size=4096 -drive if=none,id=hd,file=disk.raw,cache=none -cdrom ~/Downloads/System/ubuntu-14.04.1-server-amd64.iso

The command above uses two CPU cores and 3750 MB memory. You can tweak those settings, but remember that they are not set in stone. Your image will work just fine with 16 GB of memory and 16 CPU cores on GCE.

Another important part in the command above is that you get a TCP forward from localhost:2222 to the VM's internal port 22. You can use that to SSH into your VM while building the image.

5. Install Ubuntu on the image using the installer GUI. Things to note here:

    * Keep the installation extremely minimal. Just pick SSH from the package lists. The rest can (and should) be installed by provisioning tools.
    * Use a single partition. Do not add swap. Don't use LVM.
    * Pick the UTC timezone. This one is important, to avoid "time drift" warnings from Celery workers.

6. Configure grub with KVM kernel parameters. Edit ``/etc/default/grub`` and paste:

    | # to enable paravirtualization functionality.
    | CONFIG_KVM_GUEST=y
    | # to enable the paravirtualized clock.
    | CONFIG_KVM_CLOCK=y
    | # to enable paravirtualized PCI devices.
    | CONFIG_VIRTIO_PCI=y
    | # to enable access to paravirtualized disks.
    | CONFIG_SCSI_VIRTIO=y
    | # to enable access to the networking.
    | CONFIG_VIRTIO_NET=y

7. Configure the ``ubuntu`` user for sudo. Run a ``sudo visudo`` command and add a line::

    ubuntu  ALL=(ALL:ALL) NOPASSWD:ALL

That will allow all sudo commands by the ubuntu user and will not ask for a password.

8. Add the miami.pem public key to ``/home/ubuntu/.ssh/authorized_keys``.::

    ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCl5KNNbj1FhgYHu/mc/ZreYIoADBIXDwf8Pkch4KwinOh9WN8aHtcctFwaE8FT/5F2CBQJMsakexHLEKrEigaIxygRRn1s4zfTAEVEZTyxEoXKCcVca96RNeut6Dtyq42M1ixRbtF86RNcbGgcheiY7CEdZ81DUP6MnpGWGOR+5J6/CIRmYbD2UQjYN/LRVwwJhXonL4ijvUMrcX/EC1xdkSLM1hVYvFjtTpLv8KoMQ9KcriL3EsRHxt18eQA3M1oGayKJxZXvVnMQKL/UDGOxA8NizM6G2HihuH4wsXkdvgOeiC/6CThGRfaJ98qpNY2YkluqDuiXHxIremOvKMhP miami

9. Edit `/etc/ssh/sshd_config` and disable password-based SSH logins by changing::

    PasswordAuthentication no

10. The image is prepared. Shut down the VM: ``sudo poweroff``
11. Package the image
    
::

    $ tar -Szcf ubuntu_14.04_image.tar.gz disk.raw

The ``-S`` option is important since your disk.raw file is a sparse file.

12. `Install <https://cloud.google.com/sdk/>`_ the Google Cloud SDK.
13. Create a storage bucket
    
::

    $ gsutil mb gs://<bucket-name>

14. Upload the image to the bucket
    
::

    $ gsutil cp ubuntu_14.04_image.tar.gz gs://<bucket-name>

15. Register the image
    
::

    $ gcutil addimage ubuntu-14 gs://<bucket-name>/ubuntu_14.04_image.tar.gz

You should now see the image in the images dropdown when creating a new instance. Once you started a new instance, you can log in with a command like ``ssh ubuntu@<instance IP> -i miami.pem``. Or register the instance IP in a Fabric roledef and use the :ref:`SSH helper <fabric-ssh-helper>`.

Expanding Disk Image Size
-------------------------

You can always, create a larger image, and install Ubuntu following the steps above. But that isn't much fun. There is a way to expand the image and the filesystem inside using the `libguestfs`_ library.

.. _libguestfs: http://libguestfs.org/

Installing libguestfs on Ubuntu is pretty simple:

::

sudo apt-get install libguestfs0 libguestfs-tools

The tool we need is ``virt-resize``. It copies filesystems from a source image to a destination one, expanding/shrinking as needed. So, we first need to create the larger image:

::

    $ qemu-img create disk-100.raw 100g

And then copy the contents:

::

    $ sudo virt-resize --expand /dev/sda1 disk-10.raw disk-100.raw

The expand operation takes a while, but shouldn't be too long. Once it is done, rename your new image to `disk.raw`, and package, upload, and register it with GCE as described above.
